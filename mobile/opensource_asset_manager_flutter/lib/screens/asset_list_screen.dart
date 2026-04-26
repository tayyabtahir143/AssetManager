import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../services/token_store.dart';
import 'asset_detail_screen.dart';
import 'asset_edit_screen.dart';

class AssetListScreen extends StatefulWidget {
  final String assetType;
  final String assetLabel;

  const AssetListScreen({
    super.key,
    required this.assetType,
    required this.assetLabel,
  });

  @override
  State<AssetListScreen> createState() => _AssetListScreenState();
}

class _AssetListScreenState extends State<AssetListScreen> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String _query = '';
  String _status = 'all';
  int _filteredTotal = 0;

  Future<void> _load() async {
    setState(() => _loading = true);
    final api = ApiClient(TokenStore());
    final resp = await api.fetchAssets(
      widget.assetType,
      query: _query,
      status: _status,
      page: 1,
      perPage: 50,
    );
    if (!mounted) return;
    setState(() {
      _items = resp?.items ?? [];
      _filteredTotal = resp?.total ?? _items.length;
      _loading = false;
    });
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.assetLabel),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AssetEditScreen(
                assetType: widget.assetType,
                assetLabel: widget.assetLabel,
              ),
            ),
          );
          _load();
        },
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            decoration: const InputDecoration(
                              labelText: 'Search',
                              prefixIcon: Icon(Icons.search),
                            ),
                            onChanged: (value) => _query = value,
                          ),
                        ),
                        const SizedBox(width: 8),
                        DropdownButton<String>(
                          value: _status,
                          items: const [
                            DropdownMenuItem(value: 'all', child: Text('All')),
                            DropdownMenuItem(
                              value: 'assigned',
                              child: Text('Assigned'),
                            ),
                            DropdownMenuItem(
                              value: 'in_stock',
                              child: Text('In Stock'),
                            ),
                            DropdownMenuItem(
                              value: 'broken',
                              child: Text('Broken'),
                            ),
                            DropdownMenuItem(
                              value: 'write_off',
                              child: Text('Write Off'),
                            ),
                          ],
                          onChanged: (value) {
                            if (value == null) return;
                            setState(() => _status = value);
                            _load();
                          },
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 6,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFEAF0FF),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            '${_statusLabel()}: $_filteredTotal',
                            style: TextStyle(
                              color: colors.primary,
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        const Spacer(),
                        ElevatedButton(
                          onPressed: _load,
                          child: const Text('Apply'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : ListView.separated(
                    padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                    itemCount: _items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final item = _items[index];
                      final assetTag = item['asset_tag']?.toString() ?? '';
                      final model = item['model']?.toString() ?? '';
                      final vendor = item['vendor']?.toString() ?? '';
                      final status = item['status']?.toString() ?? '';
                      final ramType = item['ram_type']?.toString() ?? '';
                      final ramSize = item['size']?.toString() ?? '';
                      final id = (item['id'] as num?)?.toInt() ?? 0;
                      final title = widget.assetType == 'ram'
                          ? '${(ramType.isNotEmpty ? ramType : (ramSize.isNotEmpty ? ramSize : 'RAM'))} RAM'
                          : (assetTag.isNotEmpty
                                ? assetTag
                                : (model.isNotEmpty ? model : 'Asset #$id'));
                      final subtitle = [
                        vendor,
                        model,
                        status,
                      ].where((s) => s.isNotEmpty).join(' • ');
                      return Card(
                        child: ListTile(
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 6,
                          ),
                          title: Text(
                            title,
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(subtitle),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () async {
                            await Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => AssetDetailScreen(
                                  assetType: widget.assetType,
                                  assetLabel: widget.assetLabel,
                                  assetId: id,
                                ),
                              ),
                            );
                            _load();
                          },
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  String _statusLabel() {
    switch (_status) {
      case 'assigned':
        return 'Assigned devices';
      case 'in_stock':
        return 'In stock devices';
      case 'broken':
        return 'Broken devices';
      case 'write_off':
        return 'Write off devices';
      default:
        return 'Total devices';
    }
  }
}
