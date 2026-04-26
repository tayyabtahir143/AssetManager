import 'package:flutter_test/flutter_test.dart';
import 'package:opensource_asset_manager_flutter/main.dart';

void main() {
  testWidgets('App renders login screen', (WidgetTester tester) async {
    await tester.pumpWidget(const AssetManagerApp());
    expect(find.text('IT Asset Manager'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
  });
}
