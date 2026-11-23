import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:aegis_caregiver/main.dart';
import 'package:aegis_caregiver/services/api_service.dart';
import 'package:aegis_caregiver/services/call_service.dart';
import 'package:aegis_caregiver/services/history_service.dart';
import 'package:aegis_caregiver/services/preferences_service.dart';
import 'package:aegis_caregiver/services/voice_service.dart';

http.Response _json(dynamic body) => http.Response(
      jsonEncode(body),
      200,
      headers: {'content-type': 'application/json'},
    );

Map<String, String> get _prefs => {
      'patient_name': 'Arthur Siddiqui',
      'caregiver_name': 'Sarah',
      'caregiver_phone': '+1 555 010 2030',
      'relationship': 'daughter',
    };

class FakeVoice implements VoiceService {
  bool started = false;
  void Function(String, bool)? _onWords;

  @override
  Future<bool> initialize() async => true;

  @override
  Future<bool> start({
    required void Function(String words, bool finalResult) onWords,
    required void Function(String status) onStatus,
  }) async {
    _onWords = onWords;
    started = true;
    return true;
  }

  void emit(String words) => _onWords?.call(words, true);

  @override
  Future<void> stop() async {}

  @override
  Future<void> cancel() async {}

  @override
  void dispose() {}
}

Future<void> _pump(
  WidgetTester tester, {
  required http.Client client,
  Map<String, String> prefs = const {},
  VoiceService? voice,
}) async {
  SharedPreferences.resetStatic();
  SharedPreferences.setMockInitialValues(prefs);
  await tester.pumpWidget(AegisCaregiverApp(
    apiService: ApiService(baseUrl: 'http://test', client: client),
    voiceService: voice ?? NoVoiceService(),
    historyService: HistoryService(),
    preferencesService: PreferencesService(),
    callService: NoCallService(),
  ));
  await tester.pumpAndSettle();
}

http.Client _client(List<String> objects, {Map<String, dynamic>? query}) {
  return MockClient((request) async {
    switch (request.url.path) {
      case '/api/v1/health':
        return _json({'status': 'ok', 'version': '0.2.1'});
      case '/api/v1/datasets':
        return _json({
          'datasets': [
            {
              'is_active': true,
              'tracked_objects': objects,
              'anchors': ['Desk #1'],
              'rooms': ['Bedroom'],
            }
          ],
        });
      case '/api/v1/rooms':
        return _json([
          {'label': 'Bedroom', 'anchors': ['Desk #1'], 'objects': ['Laptop #3']}
        ]);
      case '/api/v1/timeline':
        return _json([
          {
            'event_type': 'placement',
            'object': 'Laptop #3',
            'summary': 'Laptop was placed on Desk #1',
          }
        ]);
      case '/api/v1/query':
        return _json(query ?? {
          'found': true,
          'resolution_mode': 'direct',
          'location_summary': 'Your laptop is on Desk #1.',
          'anchor_label': 'Desk #1',
          'candidates': [
            {'anchor_label': 'Desk #1', 'relation': 'on_surface'}
          ],
        });
      default:
        return _json({});
    }
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('first run asks for the patient name', (tester) async {
    await _pump(tester, client: _client(const []));
    expect(find.byKey(const Key('caregiver-patient-name')), findsOneWidget);
    saveButton() => tester.widget<FilledButton>(
          find.byKey(const Key('caregiver-setup-save')),
        );
    expect(saveButton().onPressed, isNull);
    await tester.enterText(
      find.byKey(const Key('caregiver-patient-name')),
      'Arthur',
    );
    await tester.pump();
    expect(saveButton().onPressed, isNotNull);
    await tester.tap(find.byKey(const Key('caregiver-setup-save')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('caregiver-patient-name')), findsNothing);
  });

  testWidgets('tiles come only from the server', (tester) async {
    await _pump(
      tester,
      prefs: _prefs,
      client: _client(['Laptop #3', 'Mystery #9']),
    );
    expect(find.text('Laptop'), findsWidgets);
    expect(find.text('Mystery'), findsOneWidget);
    expect(find.byIcon(Icons.help_outline), findsWidgets);
    expect(find.text('Keys'), findsNothing);
  });

  testWidgets('empty memory shows no hard-coded tiles', (tester) async {
    await _pump(tester, prefs: _prefs, client: _client(const []));
    expect(find.byKey(const Key('caregiver-no-objects')), findsOneWidget);
    expect(find.text('Keys'), findsNothing);
  });

  testWidgets('typed query shows a grounded answer and saves history',
      (tester) async {
    await _pump(tester, prefs: _prefs, client: _client(['Laptop #3']));
    await tester.enterText(
      find.byKey(const Key('caregiver-search-field')),
      'Where is my laptop?',
    );
    await tester.tap(find.byKey(const Key('caregiver-search-send')));
    await tester.pumpAndSettle();

    expect(find.text('Found it'), findsOneWidget);
    expect(find.text('Desk #1'), findsWidgets);
    await tester.tap(find.byKey(const Key('answer-close')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('caregiver-view-history')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Where is my laptop?'), findsOneWidget);
  });

  testWidgets('voice search fills and submits a real query', (tester) async {
    final voice = FakeVoice();
    await _pump(
      tester,
      prefs: _prefs,
      client: _client(['Laptop #3']),
      voice: voice,
    );
    await tester.tap(find.byKey(const Key('caregiver-voice-mic')));
    await tester.pump();
    expect(voice.started, isTrue);
    voice.emit('Where is my laptop?');
    await tester.pumpAndSettle();
    expect(find.text('Desk #1'), findsWidgets);
  });

  testWidgets('live badge reflects a reachable server', (tester) async {
    await _pump(tester, prefs: _prefs, client: _client(const []));
    expect(find.text('LIVE'), findsOneWidget);
    expect(find.text('NOT LIVE'), findsNothing);
  });

  testWidgets('tracking detail shows current place even without sightings',
      (tester) async {
    final client = MockClient((request) async {
      switch (request.url.path) {
        case '/api/v1/health':
          return _json({'status': 'ok'});
        case '/api/v1/datasets':
          return _json({
            'datasets': [
              {
                'is_active': true,
                'tracked_objects': ['Basket #7'],
                'anchors': [],
                'rooms': [],
              }
            ],
          });
        case '/api/v1/timeline':
          return _json([]);
        case '/api/v1/query':
          return _json({
            'found': true,
            'resolution_mode': 'direct',
            'location_summary': 'Your basket is near Desk #1.',
            'anchor_label': 'Desk #1',
            'candidates': [
              {'anchor_label': 'Desk #1', 'relation': 'next_to'}
            ],
          });
        default:
          return _json({});
      }
    });
    await _pump(tester, prefs: _prefs, client: client);
    await tester.tap(find.byKey(const Key('caregiver-tab-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('caregiver-track-basket')));
    await tester.pumpAndSettle();

    expect(find.text('LAST KNOWN LOCATION'), findsOneWidget);
    expect(find.text('Desk #1'), findsWidgets);
    expect(find.textContaining('0 sightings'), findsOneWidget);
  });

  testWidgets('history has no clear-data option and status is complete',
      (tester) async {
    tester.view.physicalSize = const Size(800, 1400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _pump(tester, prefs: _prefs, client: _client(['Laptop #3']));
    await tester.tap(find.byKey(const Key('caregiver-view-history')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('caregiver-history-clear')), findsNothing);

    await tester.tap(find.byKey(const Key('caregiver-tab-3')));
    await tester.pumpAndSettle();
    expect(find.text('System Status'), findsOneWidget);
    expect(find.text('Querying model'), findsOneWidget);
    expect(find.text('Internet status'), findsOneWidget);
    expect(find.text('Memory capacity'), findsOneWidget);
  });

  testWidgets('interaction area opens from the header on tracking tab',
      (tester) async {
    await _pump(tester, prefs: _prefs, client: _client(['Laptop #3']));
    await tester.tap(find.byKey(const Key('caregiver-tab-1')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('caregiver-interaction')));
    await tester.pumpAndSettle();
    expect(find.text('Interactions'), findsOneWidget);
    expect(find.text('Most Recent'), findsOneWidget);
    expect(find.text('Most Frequent'), findsOneWidget);
    expect(
      find.text('Most frequently interacted with objects'),
      findsOneWidget,
    );
  });

  testWidgets('interior offers enrollment and room rename', (tester) async {
    await _pump(tester, prefs: _prefs, client: _client(['Laptop #3']));
    await tester.tap(find.byKey(const Key('caregiver-tab-2')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('caregiver-enroll')), findsOneWidget);
    await tester.tap(find.byKey(const Key('caregiver-enroll')));
    await tester.pumpAndSettle();
    expect(find.text('Add a personal item'), findsOneWidget);
    expect(find.byKey(const Key('enroll-alias')), findsOneWidget);
  });

  testWidgets('tracking and interior tabs read real endpoints', (tester) async {
    await _pump(tester, prefs: _prefs, client: _client(['Laptop #3']));
    await tester.tap(find.byKey(const Key('caregiver-tab-1')));
    await tester.pumpAndSettle();
    expect(
      find.byKey(const Key('caregiver-track-laptop')),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('caregiver-track-laptop')));
    await tester.pumpAndSettle();
    expect(find.textContaining('placement'), findsWidgets);

    await tester.tap(find.byKey(const Key('caregiver-tab-2')));
    await tester.pumpAndSettle();
    expect(find.text('Bedroom'), findsOneWidget);
  });
}
