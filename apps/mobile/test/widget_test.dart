import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:aegis_mobile/main.dart';
import 'package:aegis_mobile/services/api_service.dart';

/// Server-shaped answers for the widget tests. The app itself holds no
/// canned data: without a server it says it cannot reach memory.
Map<String, dynamic> _found(
  String query,
  String instance,
  String anchor,
  String summary, {
  bool persistent = true,
}) {
  return {
    'query': query,
    'found': true,
    'item': query,
    'instance_label': instance,
    'instance_id': 1,
    'anchor_label': anchor,
    'room_label': 'Room #1',
    'relation': 'inside',
    'relative_distance_m': 0.1,
    'location_summary': summary,
    'explanation': summary,
    'last_seen_timestamp_s': 42.0,
    'last_seen_time_ago': null,
    'is_persistent_memory': persistent,
    'crop_url': null,
    'confidence': 0.82,
  };
}

final Map<String, Map<String, dynamic>> _answers = {
  'demo01|shoes': _found(
    'shoes',
    'Shoes #1 [Active Pair]',
    'Storage Cabinet #1',
    'Your shoes were last seen inside Storage Cabinet #1 in Room #1.',
  ),
  'demo04|garbage bag': _found(
    'garbage bag',
    'Garbage Bag #1',
    'Storage Cabinet #1',
    'Your garbage bag was last seen inside Storage Cabinet #1 in Room #1.',
  ),
  'Demo06-Self|water bottle': _found(
    'water bottle',
    'Bottle #1',
    'Desk #2',
    'Your bottle is on Desk #2 in Room #1.',
    persistent: false,
  ),
};

final Map<String, List<Map<String, dynamic>>> _timelines = {
  'demo04': [
    {
      'event_id': 'event_0001',
      'event_type': 'placement',
      'object': 'Garbage Bag #1',
      'destination_relation': 'inside',
      'destination_anchor': 'Storage Cabinet #1',
      'start_time': 31.6,
      'end_time': 32.0,
      'summary': 'Garbage Bag #1 was placed inside Storage Cabinet #1.',
    },
  ],
  'Demo06-Self': [
    {
      'event_id': 'event_0001',
      'event_type': 'anchor_change',
      'object': 'Bottle #1',
      'source_anchor': 'Desk #1',
      'destination_anchor': 'Desk #2',
      'start_time': 3.0,
      'end_time': 5.0,
      'summary': 'Bottle #1 moved from Desk #1 to Desk #2.',
    },
  ],
};

MockClient _server() {
  return MockClient((request) async {
    final path = request.url.path;
    final dataset = request.url.queryParameters['dataset_id'] ?? 'demo01';
    if (path == '/api/v1/query') {
      final item = request.url.queryParameters['item'] ?? '';
      final answer = _answers['$dataset|$item'] ??
          {
            'query': item,
            'found': false,
            'location_summary': "I couldn't locate any '$item' in $dataset.",
          };
      return http.Response(jsonEncode(answer), 200);
    }
    if (path == '/api/v1/timeline') {
      return http.Response(jsonEncode(_timelines[dataset] ?? []), 200);
    }
    if (path == '/api/v1/dataset/select') {
      return http.Response(jsonEncode({'status': 'ok', 'active_dataset': dataset}), 200);
    }
    return http.Response('Not Found', 404);
  });
}

ApiService _api({String dataset = 'demo01'}) =>
    ApiService(activeDatasetId: dataset, client: _server());

void main() {
  testWidgets('Patient mode queries shoes and shows the server answer', (WidgetTester tester) async {
    final apiService = _api();
    await tester.pumpWidget(AegisApp(apiService: apiService));

    expect(find.text('AEGIS'), findsOneWidget);
    expect(find.text('ACTIVE VIDEO SCENE'), findsOneWidget);
    expect(find.text('Active Shoes'), findsOneWidget);
    expect(find.text('Keys'), findsOneWidget);

    await tester.tap(find.text('Active Shoes'));
    await tester.pumpAndSettle();

    expect(find.text('LOCATED'), findsOneWidget);
    expect(find.textContaining('Storage Cabinet #1'), findsWidgets);
    expect(find.text('✦ PERSISTENT MEMORY'), findsOneWidget);
  });

  testWidgets('Unreachable server shows a message, never a location', (WidgetTester tester) async {
    final apiService = ApiService(
      client: MockClient((request) async => throw Exception('offline')),
    );
    await tester.pumpWidget(AegisApp(apiService: apiService));

    await tester.tap(find.text('Active Shoes'));
    await tester.pumpAndSettle();

    expect(find.text('NOT FOUND'), findsOneWidget);
    expect(find.textContaining("Can't reach Aegis memory"), findsWidgets);
    expect(find.textContaining('Storage Cabinet'), findsNothing);
    expect(apiService.getRecentSearches(), isEmpty);
  });

  testWidgets('Mode switcher switches to caregiver audit view', (WidgetTester tester) async {
    final apiService = _api();
    await tester.pumpWidget(AegisApp(apiService: apiService));

    await tester.tap(find.text('Caregiver Audit'));
    await tester.pumpAndSettle();

    expect(find.text('Caregiver Spatial Audit'), findsOneWidget);
    expect(find.text('Patient Recent Search History'), findsOneWidget);
    expect(find.text('Activity History Log'), findsOneWidget);
  });

  testWidgets('Caregiver view lists the patient query that was just made', (WidgetTester tester) async {
    final apiService = _api();
    await tester.pumpWidget(AegisApp(apiService: apiService));

    await tester.tap(find.text('Active Shoes'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Caregiver Audit'));
    await tester.pumpAndSettle();

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

  test('ApiService parses a null confidence and marks unreachable results', () async {
    final offline = ApiService(client: MockClient((request) async => throw Exception('x')));
    final result = await offline.queryItem('keys');
    expect(result.unreachable, isTrue);
    expect(result.found, isFalse);
    expect(result.confidence, isNull);
    expect(result.locationSummary, ApiService.unreachableMessage);

    final online = ApiService(
      client: MockClient(
        (request) async => http.Response(
          jsonEncode({'query': 'keys', 'found': true, 'location_summary': 'x', 'confidence': null}),
          200,
        ),
      ),
    );
    final parsed = await online.queryItem('keys');
    expect(parsed.unreachable, isFalse);
    expect(parsed.confidence, isNull);
  });

  testWidgets('Patient mode queries Demo04 (Empty The Trash)', (WidgetTester tester) async {
    final apiService = _api(dataset: 'demo04');
    await tester.pumpWidget(AegisApp(apiService: apiService));

    expect(find.text('Empty The Trash'), findsOneWidget);
    expect(find.text('Garbage Bag'), findsOneWidget);
    expect(find.text('Food Container'), findsOneWidget);
    expect(find.text('Plastic Bottle'), findsOneWidget);

    await tester.tap(find.text('Garbage Bag'));
    await tester.pumpAndSettle();

    expect(find.text('LOCATED'), findsOneWidget);
    expect(
      find.textContaining('Your garbage bag was last seen inside Storage Cabinet #1'),
      findsOneWidget,
    );
  });

  testWidgets('Patient mode queries Demo06-Self (Bottle Relocation Between Desks)', (WidgetTester tester) async {
    final apiService = _api(dataset: 'Demo06-Self');
    await tester.pumpWidget(AegisApp(apiService: apiService));

    expect(find.text('Bottle Relocation Between Desks'), findsOneWidget);
    expect(find.text('Water Bottle'), findsOneWidget);
    expect(find.text('Laptop'), findsOneWidget);
    expect(find.text('Cell Phone'), findsOneWidget);

    await tester.tap(find.text('Water Bottle'));
    await tester.pumpAndSettle();

    expect(find.text('LOCATED'), findsOneWidget);
    expect(find.textContaining('Desk #2'), findsWidgets);
    expect(find.textContaining('Your bottle is on Desk #2.'), findsNothing);
    expect(find.textContaining('Your bottle is on Desk #2 in Room #1.'), findsOneWidget);
  });

  testWidgets('Caregiver audit view renders timeline events from the server', (WidgetTester tester) async {
    final apiService = _api(dataset: 'demo04');
    await tester.pumpWidget(AegisApp(apiService: apiService));

    await tester.tap(find.text('Caregiver Audit'));
    await tester.pumpAndSettle();
    expect(find.text('Garbage Bag #1 was placed inside Storage Cabinet #1.'), findsOneWidget);

    await apiService.selectDataset('Demo06-Self');
    await tester.pumpWidget(AegisApp(apiService: apiService));
    await tester.pumpAndSettle();
    expect(find.text('Bottle #1 moved from Desk #1 to Desk #2.'), findsOneWidget);
  });
}
