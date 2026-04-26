import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:typed_data';
import '../services/api_client.dart';
import '../services/token_store.dart';
import '../services/asset_schema.dart';

class AssetEditScreen extends StatefulWidget {
  final String assetType;
  final String assetLabel;
  final int? assetId;

  const AssetEditScreen({
    super.key,
    required this.assetType,
    required this.assetLabel,
    this.assetId,
  });

  @override
  State<AssetEditScreen> createState() => _AssetEditScreenState();
}

class _AssetEditScreenState extends State<AssetEditScreen> {
  static const int _maxPhotos = 3;
  final Map<String, TextEditingController> _controllers = {};
  final Map<String, String> _selected = {};
  final ImagePicker _picker = ImagePicker();
  bool _saving = false;
  bool _loading = false;
  List<String> _departments = [];
  List<String> _users = [];
  List<String> _existingPhotoUrls = [];
  final Set<int> _removeExistingSlots = {};
  final List<XFile> _newPhotos = [];
  final List<String> _statusOptions = const [
    'In Stock',
    'Assigned',
    'Broken',
    'Write Off',
  ];

  @override
  void initState() {
    super.initState();
    final fields = AssetSchema.schemas[widget.assetType] ?? [];
    for (final field in fields) {
      if (_isSelectField(field.name)) {
        _selected[field.name] = '';
      } else {
        _controllers[field.name] = TextEditingController();
      }
    }
    _loadOptions();
    if (widget.assetId != null) {
      _load();
    }
  }

  bool _isSelectField(String name) {
    return name == 'status' || name == 'dept' || name == 'assigned_to' || name == 'connection';
  }

  Future<void> _loadOptions() async {
    final api = ApiClient(TokenStore());
    final departments = await api.fetchDepartments();
    final users = await api.fetchUsers();
    if (!mounted) return;
    setState(() {
      _departments = departments;
      _users = users;
    });
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final api = ApiClient(TokenStore());
    final data = await api.fetchAssetDetail(widget.assetType, widget.assetId!);
    if (data != null) {
      for (final entry in _controllers.entries) {
        entry.value.text = data[entry.key]?.toString() ?? '';
      }
      for (final entry in _selected.entries) {
        _selected[entry.key] = data[entry.key]?.toString() ?? '';
      }
      final urls = (data['photo_urls'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .where((item) => item.isNotEmpty)
          .toList();
      _existingPhotoUrls = urls;
      _removeExistingSlots.clear();
      _newPhotos.clear();
    }
    if (!mounted) return;
    setState(() => _loading = false);
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final payload = <String, dynamic>{};
      _controllers.forEach((key, controller) {
        payload[key] = controller.text.trim();
      });
      _selected.forEach((key, value) {
        payload[key] = value;
      });
      final api = ApiClient(TokenStore());
      bool ok = false;
      int? targetId = widget.assetId;
      if (widget.assetId == null) {
        targetId = await api.createAssetAndGetId(widget.assetType, payload);
        ok = targetId != null;
      } else {
        ok = await api.updateAsset(widget.assetType, widget.assetId!, payload);
      }
      if (ok && targetId != null) {
        final removeSlots = _removeExistingSlots.toList()..sort();
        final uploadFiles = <UploadPhoto>[];
        for (final photo in _newPhotos) {
          final bytes = await photo.readAsBytes();
          final name = photo.name;
          final dot = name.lastIndexOf('.');
          final ext = dot >= 0 ? name.substring(dot).toLowerCase() : '';
          final safeExt = ext.isNotEmpty ? ext : '.jpg';
          uploadFiles.add(
            UploadPhoto(
              filename: 'asset-photo-${DateTime.now().microsecondsSinceEpoch}$safeExt',
              bytes: bytes,
            ),
          );
        }
        if (removeSlots.isNotEmpty || uploadFiles.isNotEmpty) {
          ok = await api.updateAssetPhotos(
            widget.assetType,
            targetId,
            files: uploadFiles,
            removeSlots: removeSlots,
          );
        }
      }
      if (!mounted) return;
      if (ok) {
        Navigator.of(context).pop();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Failed to save asset photos. Please try again.')),
        );
      }
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Something went wrong while saving. Please try again.')),
      );
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  int get _remainingPhotoCapacity {
    final keptExisting = _existingPhotoUrls.length - _removeExistingSlots.length;
    return (_maxPhotos - keptExisting - _newPhotos.length).clamp(0, _maxPhotos);
  }

  Future<void> _pickPhoto(ImageSource source) async {
    if (_remainingPhotoCapacity <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Maximum 3 photos allowed per asset.')),
      );
      return;
    }
    final image = await _picker.pickImage(
      source: source,
      imageQuality: 85,
      maxWidth: 1920,
    );
    if (!mounted || image == null) return;
    setState(() {
      _newPhotos.add(image);
    });
  }

  @override
  Widget build(BuildContext context) {
    final fields = AssetSchema.schemas[widget.assetType] ?? [];
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.assetId == null ? 'Add ${widget.assetLabel}' : 'Edit ${widget.assetLabel}'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.assetId == null ? 'Create new ${widget.assetLabel}' : 'Update ${widget.assetLabel}',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Fill all required details below.',
                          style: TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                        ),
                        const SizedBox(height: 14),
                        if (fields.isEmpty)
                          const Text('No editable fields configured for this asset type.'),
                        for (final field in fields)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: _buildField(field),
                          ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed: _saving ? null : () => _pickPhoto(ImageSource.camera),
                                icon: const Icon(Icons.photo_camera_outlined),
                                label: const Text('Take Photo'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed: _saving ? null : () => _pickPhoto(ImageSource.gallery),
                                icon: const Icon(Icons.photo_library_outlined),
                                label: const Text('Gallery'),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Photos: ${_existingPhotoUrls.length - _removeExistingSlots.length + _newPhotos.length}/$_maxPhotos',
                          style: const TextStyle(fontSize: 12, color: Color(0xFF64748B)),
                        ),
                        const SizedBox(height: 8),
                        _buildPhotoPreviewSection(),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                ElevatedButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: const Icon(Icons.save_outlined),
                  label: _saving
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Save changes'),
                ),
              ],
            ),
    );
  }

  Widget _buildPhotoPreviewSection() {
    final widgets = <Widget>[];
    for (var i = 0; i < _existingPhotoUrls.length; i++) {
      final slot = i + 1;
      if (_removeExistingSlots.contains(slot)) continue;
      widgets.add(
        _PhotoCard(
          child: Image.network(
            _existingPhotoUrls[i],
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => const Center(child: Icon(Icons.broken_image_outlined)),
          ),
          onRemove: _saving
              ? null
              : () {
                  setState(() => _removeExistingSlots.add(slot));
                },
          caption: 'Saved photo $slot',
        ),
      );
    }
    for (var i = 0; i < _newPhotos.length; i++) {
      widgets.add(
        _PhotoCard(
          child: _XFilePreview(file: _newPhotos[i]),
          onRemove: _saving
              ? null
              : () {
                  setState(() => _newPhotos.removeAt(i));
                },
          caption: 'New photo',
        ),
      );
    }
    if (widgets.isEmpty) {
      return const Text(
        'No photos selected yet. Use camera or gallery to attach up to 3 images.',
        style: TextStyle(fontSize: 12, color: Color(0xFF64748B)),
      );
    }
    return Wrap(spacing: 10, runSpacing: 10, children: widgets);
  }

  Widget _buildField(FieldDef field) {
    if (field.name == 'status') {
      final options = _statusOptions;
      final current = _selected[field.name] ?? '';
      final value = options.contains(current) ? current : null;
      return DropdownButtonFormField<String>(
        value: value,
        items: options
            .map((item) => DropdownMenuItem(value: item, child: Text(item)))
            .toList(),
        onChanged: (value) => setState(() => _selected[field.name] = value ?? ''),
        decoration: InputDecoration(
          labelText: field.label,
          border: const OutlineInputBorder(),
        ),
      );
    }
    if (field.name == 'dept') {
      final items = [''] + _departments;
      final current = _selected[field.name] ?? '';
      final value = items.contains(current) ? current : '';
      return DropdownButtonFormField<String>(
        value: value,
        items: items
            .map((item) => DropdownMenuItem(
                  value: item,
                  child: Text(item.isEmpty ? '-' : item),
                ))
            .toList(),
        onChanged: (value) => setState(() => _selected[field.name] = value ?? ''),
        decoration: InputDecoration(
          labelText: field.label,
          border: const OutlineInputBorder(),
        ),
      );
    }
    if (field.name == 'assigned_to') {
      final items = ['free'] + _users;
      final current = _selected[field.name] ?? 'free';
      final value = items.contains(current) ? current : 'free';
      return DropdownButtonFormField<String>(
        value: value,
        items: items
            .map((item) => DropdownMenuItem(
                  value: item,
                  child: Text(item == 'free' ? '-' : item),
                ))
            .toList(),
        onChanged: (value) => setState(() => _selected[field.name] = value ?? 'free'),
        decoration: InputDecoration(
          labelText: field.label,
          border: const OutlineInputBorder(),
        ),
      );
    }
    if (field.name == 'connection') {
      const options = ['Wired', 'Wireless'];
      final current = _selected[field.name] ?? '';
      final value = options.contains(current) ? current : null;
      return DropdownButtonFormField<String>(
        value: value,
        items: options
            .map((item) => DropdownMenuItem(value: item, child: Text(item)))
            .toList(),
        onChanged: (value) => setState(() => _selected[field.name] = value ?? ''),
        decoration: InputDecoration(
          labelText: field.label,
          border: const OutlineInputBorder(),
        ),
      );
    }
    return TextField(
      controller: _controllers[field.name],
      decoration: InputDecoration(
        labelText: field.label,
        border: const OutlineInputBorder(),
      ),
    );
  }
}

class _XFilePreview extends StatelessWidget {
  const _XFilePreview({required this.file});

  final XFile file;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Uint8List>(
      future: file.readAsBytes(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator(strokeWidth: 2));
        }
        return Image.memory(
          snapshot.data!,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => const Center(child: Icon(Icons.image_not_supported_outlined)),
        );
      },
    );
  }
}

class _PhotoCard extends StatelessWidget {
  const _PhotoCard({
    required this.child,
    required this.onRemove,
    required this.caption,
  });

  final Widget child;
  final VoidCallback? onRemove;
  final String caption;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 110,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: SizedBox(height: 90, width: 110, child: child),
          ),
          const SizedBox(height: 6),
          Text(caption, style: const TextStyle(fontSize: 11, color: Color(0xFF64748B))),
          TextButton.icon(
            onPressed: onRemove,
            style: TextButton.styleFrom(padding: EdgeInsets.zero, minimumSize: const Size(0, 30)),
            icon: const Icon(Icons.delete_outline, size: 16),
            label: const Text('Remove', style: TextStyle(fontSize: 12)),
          ),
        ],
      ),
    );
  }
}
