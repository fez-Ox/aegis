import 'package:flutter_test/flutter_test.dart';
import 'package:aegis_mobile/main.dart';
import 'package:aegis_mobile/services/api_service.dart';

void main() {
  testWidgets('Aegis dementia patient mode renders and executes shoes query', (WidgetTester tester) async {
    final apiService = ApiService();
    await tester.pumpWidget(AegisApp(apiService: apiService));

    // Verify initial branding and instruction
    expect(find.text('AEGIS'), findsOneWidget);
    expect(find.text('Tap an item to find where it is right now'), findsOneWidget);
    expect(find.text('Shoes'), findsOneWidget);
    expect(find.text('Keys'), findsOneWidget);

    // Tap on Shoes tile to trigger recall
    await tester.tap(find.text('Shoes'));
    await tester.pumpAndSettle();

    // Verify dementia result card appears with plain-English location
    expect(find.text('LOCATED'), findsOneWidget);
    expect(find.textContaining('Storage Cabinet #1'), findsWidgets);
    expect(find.text('✦ PERSISTENT MEMORY'), findsOneWidget);
  });

  testWidgets('Aegis mode switcher switches to caregiver audit view', (WidgetTester tester) async {
    final apiService = ApiService();
    await tester.pumpWidget(AegisApp(apiService: apiService));

    // Switch to Caregiver Audit
    await tester.tap(find.text('Caregiver Audit'));
    await tester.pumpAndSettle();

    // Verify caregiver view renders
    expect(find.text('Caregiver Spatial Audit'), findsOneWidget);
    expect(find.text('Patient Recent Search History'), findsOneWidget);
    expect(find.text('Activity History Log'), findsOneWidget);
  });

  testWidgets('Caregiver view displays recent 3 patient recall queries', (WidgetTester tester) async {
    final apiService = ApiService();
    await tester.pumpWidget(AegisApp(apiService: apiService));

    // Switch to Caregiver Audit
    await tester.tap(find.text('Caregiver Audit'));
    await tester.pumpAndSettle();

    // Verify recent 3 searches header and seed items are visible
    expect(find.text('Patient Recent Search History'), findsOneWidget);
    expect(find.text('3 Recent'), findsOneWidget);
    expect(find.text('Shoes'), findsOneWidget);
    expect(find.text('Keys'), findsOneWidget);
    expect(find.text('Glasses'), findsOneWidget);
  });

  test('ApiService getRecentSearches strictly limits returned count to 3', () {
    final apiService = ApiService();
    final recent = apiService.getRecentSearches(limit: 3);
    expect(recent.length, lessThanOrEqualTo(3));
  });
}
