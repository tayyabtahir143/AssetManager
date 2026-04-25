import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import '../models/api_models.dart';
import 'token_store.dart';

class UploadPhoto {
  const UploadPhoto({
    required this.filename,
    required this.bytes,
  });

  final String filename;
  final Uint8List bytes;
}

class ApiClient {
  ApiClient(this.store);

  final TokenStore store;

  Future<String> _baseUrl() async {
    final raw = await store.getBaseUrl();
    if (raw.endsWith('/')) return raw;
    return '$raw/';
  }

  Future<http.Response> _request(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? body,
    Map<String, String>? params,
    bool retry = true,
    bool includeAuth = true,
  }) async {
    final base = await _baseUrl();
    final uri = Uri.parse(base + path).replace(queryParameters: params);
    final headers = <String, String>{
      'Content-Type': 'application/json',
    };
    if (includeAuth) {
      final token = await store.getAccessToken();
      if (token != null && token.isNotEmpty) {
        headers['Authorization'] = 'Bearer $token';
      }
    }
    http.Response response;
    switch (method) {
      case 'POST':
        response = await http
            .post(uri, headers: headers, body: jsonEncode(body ?? {}))
            .timeout(const Duration(seconds: 20));
        break;
      case 'PUT':
        response = await http
            .put(uri, headers: headers, body: jsonEncode(body ?? {}))
            .timeout(const Duration(seconds: 20));
        break;
      case 'DELETE':
        response = await http.delete(uri, headers: headers).timeout(const Duration(seconds: 20));
        break;
      default:
        response = await http.get(uri, headers: headers).timeout(const Duration(seconds: 20));
    }
    if (response.statusCode == 401 && retry) {
      final refreshed = await refreshToken();
      if (refreshed) {
        return _request(path, method: method, body: body, params: params, retry: false);
      }
    }
    return response;
  }

  Future<TokenResponse?> login(String username, String password) async {
    final response = await _request(
      'api/auth/login',
      method: 'POST',
      body: {'username': username, 'password': password},
      retry: false,
      includeAuth: false,
    );
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return TokenResponse.fromJson(data);
    }
    return null;
  }

  Future<bool> refreshToken() async {
    final refresh = await store.getRefreshToken();
    if (refresh == null || refresh.isEmpty) return false;
    final response = await _request(
      'api/auth/refresh',
      method: 'POST',
      body: {'refresh_token': refresh},
      retry: false,
      includeAuth: false,
    );
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final token = TokenResponse.fromJson(data);
      await store.setTokens(token.accessToken, token.refreshToken);
      return true;
    }
    await store.clearTokens();
    return false;
  }

  Future<List<AssetTypeDto>> fetchAssetTypes() async {
    final response = await _request('api/asset-types');
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as List<dynamic>;
      return data.map((item) => AssetTypeDto.fromJson(item)).toList();
    }
    return [];
  }

  Future<List<String>> fetchUsers() async {
    final response = await _request('api/users');
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as List<dynamic>;
      return data.map((item) => item.toString()).toList();
    }
    return [];
  }

  Future<List<String>> fetchDepartments() async {
    final response = await _request('api/departments');
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as List<dynamic>;
      return data.map((item) => item.toString()).toList();
    }
    return [];
  }

  Future<AssetListResponse?> fetchAssets(
    String assetType, {
    String? query,
    String? status,
    int page = 1,
    int perPage = 50,
  }) async {
    final response = await _request(
      'api/assets/$assetType',
      params: {
        'q': query ?? '',
        'status': status ?? 'all',
        'page': page.toString(),
        'per_page': perPage.toString(),
      },
    );
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return AssetListResponse.fromJson(data);
    }
    return null;
  }

  Future<Map<String, dynamic>?> fetchAssetDetail(String assetType, int id) async {
    final response = await _request('api/assets/$assetType/$id');
    if (response.statusCode == 200) {
      final data = Map<String, dynamic>.from(jsonDecode(response.body) as Map);
      final token = await store.getAccessToken();
      final photoUrls = (data['photo_urls'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .where((item) => item.isNotEmpty)
          .toList();
      if (token != null && token.isNotEmpty && photoUrls.isNotEmpty) {
        data['photo_urls'] = photoUrls.map((url) {
          final separator = url.contains('?') ? '&' : '?';
          return '$url${separator}access_token=$token';
        }).toList();
      }
      return data;
    }
    return null;
  }

  Future<bool> createAsset(String assetType, Map<String, dynamic> payload) async {
    final response = await _request('api/assets/$assetType', method: 'POST', body: payload);
    return response.statusCode == 201;
  }

  Future<int?> createAssetAndGetId(String assetType, Map<String, dynamic> payload) async {
    final response = await _request('api/assets/$assetType', method: 'POST', body: payload);
    if (response.statusCode == 201) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final idValue = data['id'];
      if (idValue is int) return idValue;
      if (idValue is String) return int.tryParse(idValue);
    }
    return null;
  }

  Future<bool> updateAsset(String assetType, int id, Map<String, dynamic> payload) async {
    final response = await _request('api/assets/$assetType/$id', method: 'PUT', body: payload);
    return response.statusCode == 200;
  }

  Future<bool> updateAssetPhotos(
    String assetType,
    int id, {
    List<UploadPhoto> files = const [],
    List<int> removeSlots = const [],
    bool retry = true,
  }) async {
    try {
      final base = await _baseUrl();
      final uri = Uri.parse('${base}api/assets/$assetType/$id/photos');
      final request = http.MultipartRequest('POST', uri);
      final token = await store.getAccessToken();
      if (token != null && token.isNotEmpty) {
        request.headers['Authorization'] = 'Bearer $token';
      }
      if (removeSlots.isNotEmpty) {
        request.fields['remove_slots'] = removeSlots.join(',');
      }
      for (final file in files) {
        request.files.add(
          http.MultipartFile.fromBytes(
            'photos',
            file.bytes,
            filename: file.filename,
          ),
        );
      }
      final streamed = await request.send().timeout(const Duration(seconds: 30));
      if (streamed.statusCode == 401 && retry) {
        final refreshed = await refreshToken();
        if (refreshed) {
          return updateAssetPhotos(
            assetType,
            id,
            files: files,
            removeSlots: removeSlots,
            retry: false,
          );
        }
      }
      return streamed.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> deleteAsset(String assetType, int id) async {
    final response = await _request('api/assets/$assetType/$id', method: 'DELETE');
    return response.statusCode == 200;
  }
}
