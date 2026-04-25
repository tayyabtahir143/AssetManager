import 'package:flutter/material.dart';
import '../models/api_models.dart';
import '../services/api_client.dart';
import '../services/token_store.dart';
import 'asset_list_screen.dart';
import 'login_screen.dart';

class AssetTypesScreen extends StatefulWidget {
  const AssetTypesScreen({super.key});

  @override
  State<AssetTypesScreen> createState() => _AssetTypesScreenState();
}

class _AssetTypesScreenState extends State<AssetTypesScreen> {
  List<AssetTypeDto> _items = [];
  bool _loading = true;
  Map<String, int> _availableByType = {};
  int _availableTotal = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final api = ApiClient(TokenStore());
    final items = await api.fetchAssetTypes();
    final entries = await Future.wait(
      items.map((item) async {
        final resp = await api.fetchAssets(
          item.key,
          status: 'in_stock',
          page: 1,
          perPage: 1,
        );
        return MapEntry(item.key, resp?.total ?? 0);
      }),
    );
    final counts = {for (final entry in entries) entry.key: entry.value};
    final total = counts.values.fold<int>(0, (sum, value) => sum + value);
    if (!mounted) return;
    setState(() {
      _items = items;
      _availableByType = counts;
      _availableTotal = total;
      _loading = false;
    });
  }

  Future<void> _logout() async {
    await TokenStore().clearTokens();
    if (!mounted) return;
    Navigator.of(
      context,
    ).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Image.asset('assets/icon.png', width: 28, height: 28),
            const SizedBox(width: 10),
            const Text('Asset Command Center'),
          ],
        ),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
          IconButton(onPressed: _logout, icon: const Icon(Icons.logout)),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(20),
                      gradient: const LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [Color(0xFF3459E6), Color(0xFF5B7CFA)],
                      ),
                    ),
                    padding: const EdgeInsets.all(18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Available Stock',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '$_availableTotal',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 32,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Items currently in inventory',
                          style: TextStyle(color: Colors.white70, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                const Text(
                  'Asset Types',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                ..._items.map((item) {
                  final count = _availableByType[item.key] ?? 0;
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Card(
                      child: ListTile(
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 6,
                        ),
                        title: Text(
                          item.label,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        subtitle: Text(
                          '$count available',
                          style: TextStyle(color: colors.primary),
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => AssetListScreen(
                                assetType: item.key,
                                assetLabel: item.label,
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                  );
                }),
              ],
            ),
    );
  }
}
