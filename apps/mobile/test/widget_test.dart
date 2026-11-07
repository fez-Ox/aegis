import 'package:flutter_test/flutter_test.dart';
import 'package:aegis_mobile/main.dart';
import 'package:aegis_mobile/services/api_service.dart';

void main() {
  testWidgets('Aegis dementia patient mode renders and executes shoes query', (WidgetTester tester) async {
    final apiService = ApiService();
    await tester.pumpWidget(AegisApp(apiService: apiService));

    // Verify initial branding and active-scene controls
    expect(find.text('AEGIS'), findsOneWidget);
    expect(find.text('ACTIVE VIDEO SCENE'), findsOneWidget);
    expect(find.text('Active Shoes'), findsOneWidget);
    expect(find.text('Keys'), findsOneWidget);

    // Tap on the shoes tile to trigger recall
    await tester.tap(find.text('Active Shoes'));
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

    // Verify the dataset-scoped search history is visible
    expect(find.text('Patient Recent Search History'), findsOneWidget);
    expect(find.text('1 Recent'), findsOneWidget);
    expect(find.text('Shoes'), findsOneWidget);
  });

  test('ApiService getRecentSearches strictly limits returned count to 3', () {
    final apiService = ApiService();
    final recent = apiService.getRecentSearches(limit: 3);
    expect(recent.length, lessThanOrEqualTo(3));
  });

  test('ApiService adds the default LAN port to a bare host', () {
    final apiService = ApiService();
    apiService.updateBaseUrl('192.168.10.11');
    expect(apiService.baseUrl, 'http://192.168.10.11:8000');
  });

  testWidgets('Patient mode dynamically configures and queries Demo04 (Empty The Trash)', (WidgetTester tester) async {
    final apiService = ApiService(activeDatasetId: 'demo04');
    await tester.pumpWidget(AegisApp(apiService: apiService));

    // Verify scene branding
    expect(find.text('Empty The Trash'), findsOneWidget);
    expect(find.text('Garbage Bag'), findsOneWidget);
    expect(find.text('Food Container'), findsOneWidget);
    expect(find.text('Plastic Bottle'), findsOneWidget);

    // Tap on Garbage Bag to query
    await tester.tap(find.text('Garbage Bag'));
    await tester.pumpAndSettle();

    // Verify result card
    expect(find.text('LOCATED'), findsOneWidget);
    expect(find.textContaining('Storage Cabinet #1'), findsWidgets);
    expect(find.textContaining('Your trash is near Storage Cabinet #1.'), findsOneWidget);
  });

  testWidgets('Patient mode dynamically configures and queries Demo06-Self (Bottle Relocation Between Desks)', (WidgetTester tester) async {
    final apiService = ApiService(activeDatasetId: 'Demo06-Self');
    await tester.pumpWidget(AegisApp(apiService: apiService));

    // Verify scene branding
    expect(find.text('Bottle Relocation Between Desks'), findsOneWidget);
    expect(find.text('Water Bottle'), findsOneWidget);
    expect(find.text('Laptop'), findsOneWidget);
    expect(find.text('Cell Phone'), findsOneWidget);

    // Tap on Water Bottle to query
    await tester.tap(find.text('Water Bottle'));
    await tester.pumpAndSettle();

    // Verify result card
    expect(find.text('LOCATED'), findsOneWidget);
    expect(find.textContaining('Desk #2'), findsWidgets);
    expect(find.textContaining('Your bottle is currently resting on Desk #2.'), findsOneWidget);
  });

  testWidgets('Caregiver audit view renders timeline events for Demo04 and Demo06-Self', (WidgetTester tester) async {
    final apiService = ApiService(activeDatasetId: 'demo04');
    await tester.pumpWidget(AegisApp(apiService: apiService));

    // Switch to Caregiver Audit
    await tester.tap(find.text('Caregiver Audit'));
    await tester.pumpAndSettle();

    // Verify Demo04 events
    expect(find.text('Garbage Bag #1 was placed inside Storage Cabinet #1.'), findsOneWidget);
    expect(find.text('Food Container #2 was placed inside Storage Cabinet #1.'), findsOneWidget);

    // Switch active dataset to Demo06-Self on ApiService and re-pump
    await apiService.selectDataset('Demo06-Self');
    await tester.pumpWidget(AegisApp(apiService: apiService));
    await tester.pumpAndSettle();

    // Verify Demo06-Self events
    expect(find.text('Bottle #1 was moved from Desk #1 to Desk #2.'), findsOneWidget);
  });
}

