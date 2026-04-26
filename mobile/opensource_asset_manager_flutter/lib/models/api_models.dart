class TokenResponse {
  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final int expiresIn;

  TokenResponse({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.expiresIn,
  });

  factory TokenResponse.fromJson(Map<String, dynamic> json) {
    return TokenResponse(
      accessToken: json['access_token'] ?? '',
      refreshToken: json['refresh_token'] ?? '',
      tokenType: json['token_type'] ?? 'Bearer',
      expiresIn: json['expires_in'] ?? 0,
    );
  }
}

class AssetTypeDto {
  final String key;
  final String label;

  AssetTypeDto({required this.key, required this.label});

  factory AssetTypeDto.fromJson(Map<String, dynamic> json) {
    return AssetTypeDto(
      key: json['key'] ?? '',
      label: json['label'] ?? '',
    );
  }
}

class AssetListResponse {
  final List<Map<String, dynamic>> items;
  final int page;
  final int perPage;
  final int total;

  AssetListResponse({
    required this.items,
    required this.page,
    required this.perPage,
    required this.total,
  });

  factory AssetListResponse.fromJson(Map<String, dynamic> json) {
    final rawItems = (json['items'] as List<dynamic>? ?? [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
    return AssetListResponse(
      items: rawItems,
      page: json['page'] ?? 1,
      perPage: json['per_page'] ?? 25,
      total: json['total'] ?? rawItems.length,
    );
  }
}
