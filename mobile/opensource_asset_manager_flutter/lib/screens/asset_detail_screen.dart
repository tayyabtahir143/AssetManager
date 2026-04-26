import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../services/token_store.dart';
import 'asset_edit_screen.dart';

class AssetDetailScreen extends StatefulWidget {
  final String assetType;
  final String assetLabel;
  final int assetId;

  const AssetDetailScreen({
    super.key,
    required this.assetType,
    required this.assetLabel,
    required this.assetId,
  });

  @override
  State<AssetDetailScreen> createState() => _AssetDetailScreenState();
}

class _AssetDetailScreenState extends State<AssetDetailScreen> {
  Map<String, dynamic> _data = {};
  bool _loading = true;
  List<String> _photoUrls = [];

  Future<void> _load() async {
    setState(() => _loading = true);
    final api = ApiClient(TokenStore());
    final response = await api.fetchAssetDetail(
      widget.assetType,
      widget.assetId,
    );
    if (!mounted) return;
    setState(() {
      _data = response ?? {};
      _photoUrls = (_data['photo_urls'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .where((item) => item.isNotEmpty)
          .toList();
      _loading = false;
    });
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _delete() async {
    final api = ApiClient(TokenStore());
    await api.deleteAsset(widget.assetType, widget.assetId);
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.assetLabel} Detail'),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit),
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => AssetEditScreen(
                    assetType: widget.assetType,
                    assetLabel: widget.assetLabel,
                    assetId: widget.assetId,
                  ),
                ),
              );
              _load();
            },
          ),
          IconButton(icon: const Icon(Icons.delete), onPressed: _delete),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_photoUrls.isNotEmpty) ...[
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'PHOTOS',
                            style: TextStyle(
                              fontSize: 12,
                              letterSpacing: 0.6,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF475569),
                            ),
                          ),
                          const SizedBox(height: 10),
                          Wrap(
                            spacing: 10,
                            runSpacing: 10,
                            children: _photoUrls
                                .map(
                                  (url) => ClipRRect(
                                    borderRadius: BorderRadius.circular(10),
                                    child: Image.network(
                                      url,
                                      width: 130,
                                      height: 100,
                                      fit: BoxFit.cover,
                                      errorBuilder: (_, __, ___) => Container(
                                        width: 130,
                                        height: 100,
                                        color: const Color(0xFFE2E8F0),
                                        child: const Icon(
                                          Icons.broken_image_outlined,
                                        ),
                                      ),
                                    ),
                                  ),
                                )
                                .toList(),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                ],
                ..._data.entries
                    .where(
                      (entry) => entry.key != 'id' && entry.key != 'photo_urls',
                    )
                    .map(
                      (entry) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Card(
                          child: ListTile(
                            title: Text(
                              entry.key.replaceAll('_', ' ').toUpperCase(),
                              style: const TextStyle(
                                fontSize: 12,
                                letterSpacing: 0.6,
                                fontWeight: FontWeight.w700,
                                color: Color(0xFF475569),
                              ),
                            ),
                            subtitle: Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Text(
                                entry.value?.toString() ?? '-',
                                style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF0F172A),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    )
                    .toList(),
              ],
            ),
    );
  }
}
