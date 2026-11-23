import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:aegis_patient/main.dart';
import 'package:aegis_patient/services/api_service.dart';
import 'package:aegis_patient/services/call_service.dart';
import 'package:aegis_patient/services/preferences_service.dart';
import 'package:aegis_patient/services/voice_service.dart';

http.Response _json(Map<String, dynamic> body) => http.Response(
      jsonEncode(body),
      200,
      headers: {'content-type': 'application/json'},
    );

Map<String, String> get _configuredPrefs => {
      'patient_name': 'Arthur',
      'caregiver_name': 'Sarah',
      'caregiver_phone': '+1 555 010 2030',
      'relationship': 'Your daughter',
    };

class FakeVoiceService implements VoiceService {
  void Function(String, bool)? _onWords;
  bool started = false;

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

class FakeCallService implements CallService {
  final List<String> calls = [];
  final List<String> messages = [];

  @override
  Future<bool> call(String phone) async {
    calls.add(phone);
    return true;
  }

  @override
  Future<bool> message(String phone, String body) async {
    messages.add('$phone: $body');
    return true;
  }
}

Future<void> _pumpApp(
  WidgetTester tester, {
  required http.Client client,
  VoiceService? voice,
  FakeCallService? call,
  Map<String, String> prefs = const {},
}) async {
  // The plugin caches its instance between tests; reset before re-seeding.
  // ignore: invalid_use_of_visible_for_testing_member
  SharedPreferences.resetStatic();
  SharedPreferences.setMockInitialValues(prefs);
  await tester.pumpWidget(AegisPatientApp(
    apiService: ApiService(baseUrl: 'http://test', client: client),
    voiceService: voice ?? NoVoiceService(),
    callService: call ?? FakeCallService(),
    preferencesService: PreferencesService(),
  ));
  await tester.pumpAndSettle();
}

Map<String, dynamic> _datasetsResponse(List<String> objects) => {
      'datasets': [
        {'is_active': true, 'tracked_objects': objects},
      ],
    };

Map<String, dynamic> _foundResponse({
  required String place,
  String mode = 'direct',
  bool ambiguous = false,
  List<Map<String, dynamic>>? candidates,
}) {
  return {
    'query': 'keys',
    'found': true,
    'resolution_mode': mode,
    'is_ambiguous': ambiguous,
    'location_summary': 'Your keys are on the $place.',
    'anchor_label': place,
    'crop_url': '/api/v1/crops/1',
    'candidates': candidates ??
        [
          {
            'anchor_label': place,
            'room_label': 'Kitchen',
            'relation': 'on the counter',
            'last_seen_at': 'Seen 10 minutes ago',
            'crop_url': '/api/v1/crops/1',
            'score': 0.9,
          }
        ],
  };
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('first run requires a caregiver phone number', (tester) async {
    await _pumpApp(
      tester,
      client: MockClient((_) async => _json({'found': false})),
    );

    expect(find.byKey(const Key('onboarding-phone')), findsOneWidget);
    FilledButton save = tester.widget(
      find.byKey(const Key('onboarding-save')),
    );
    expect(save.onPressed, isNull, reason: 'cannot save without a number');

    await tester.enterText(
      find.byKey(const Key('onboarding-phone')),
      '+1 555 010 2030',
    );
    await tester.pump();
    save = tester.widget(find.byKey(const Key('onboarding-save')));
    expect(save.onPressed, isNotNull);

    await tester.tap(find.byKey(const Key('onboarding-save')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('onboarding-phone')), findsNothing);
    expect(find.textContaining('Call'), findsWidgets);
  });

  testWidgets('typed question shows a grounded answer with a friendly badge',
      (tester) async {
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/query') {
          expect(request.url.queryParameters['item'], 'keys');
        }
        return _json(_foundResponse(place: 'Kitchen counter'));
      }),
    );

    await tester.enterText(
      find.byKey(const Key('ask-field')),
      'Where are my keys?',
    );
    await tester.tap(find.byKey(const Key('ask-send')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('resolution-badge')), findsOneWidget);
    expect(find.text('Found it'), findsOneWidget);
    expect(find.text('Kitchen counter'), findsOneWidget);
    expect(find.byKey(const Key('answer-close')), findsOneWidget);
  });

  testWidgets('tapping an object with no history says so plainly', (tester) async {
    tester.view.physicalSize = const Size(800, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/datasets') {
          return _json(_datasetsResponse(['Keys #1']));
        }
        if (request.url.path == '/api/v1/query') {
          expect(request.url.queryParameters['item'], 'Keys');
        }
        return _json({
          'query': 'Keys',
          'found': false,
          'location_summary': 'I couldn’t locate any Keys.',
        });
      }),
    );

    await tester.tap(find.byKey(const Key('object-keys')));
    await tester.pumpAndSettle();

    expect(
      find.text(ApiService.notFoundMessage),
      findsOneWidget,
    );
    expect(find.text('Found it'), findsNothing);
  });

  testWidgets('quick tiles reflect objects the server actually remembers',
      (tester) async {
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/datasets') {
          return _json({
            'datasets': [
              {
                'is_active': true,
                'tracked_objects': ['Cell Phone #4', 'Book #2', 'Laptop #3'],
              }
            ],
          });
        }
        return _json(_foundResponse(place: 'Desk #1'));
      }),
    );

    expect(find.text('Cell Phone'), findsOneWidget);
    expect(find.text('Book'), findsOneWidget);
    expect(find.text('Laptop'), findsOneWidget);
    expect(find.byKey(const Key('object-keys')), findsNothing);
  });

  testWidgets('empty memory shows no hard-coded object cards', (tester) async {
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/datasets') {
          return _json(_datasetsResponse(const []));
        }
        return _json(_foundResponse(place: 'Desk #1'));
      }),
    );

    expect(find.byKey(const Key('no-objects')), findsOneWidget);
    expect(find.text('Keys'), findsNothing);
    expect(find.text('Mug'), findsNothing);
  });

  testWidgets('unrecognised items get a question-mark icon', (tester) async {
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/datasets') {
          return _json(_datasetsResponse(['Unicorn #1']));
        }
        return _json(_foundResponse(place: 'Desk #1'));
      }),
    );

    expect(find.text('Unicorn'), findsOneWidget);
    expect(find.byIcon(Icons.help_outline), findsWidgets);
  });

  testWidgets('ambiguous answers show candidate places', (tester) async {
    // A tall surface keeps the lower object tiles on-screen without scrolling.
    tester.view.physicalSize = const Size(800, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/datasets') {
          return _json(_datasetsResponse(['Mug #1']));
        }
        return _json(_foundResponse(
          place: 'Dish rack',
          mode: 'disambiguate',
          ambiguous: true,
          candidates: [
            {
              'anchor_label': 'Dish rack',
              'relation': 'beside the sink',
              'crop_url': '/api/v1/crops/1',
            },
            {
              'anchor_label': 'Kitchen counter',
              'relation': 'next to the kettle',
              'crop_url': '/api/v1/crops/2',
            },
          ],
        ));
      }),
    );

    await tester.tap(find.byKey(const Key('object-mug')));
    await tester.pumpAndSettle();

    expect(
      find.text('I’m not sure — which one?'),
      findsOneWidget,
    );
    expect(find.text('Dish rack'), findsOneWidget);
    expect(find.text('Kitchen counter'), findsOneWidget);
    expect(find.text('Most likely'), findsOneWidget);
  });

  testWidgets('voice search transcribes into a real query', (tester) async {
    final voice = FakeVoiceService();
    String? asked;
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      voice: voice,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/query') {
          asked = request.url.queryParameters['item'];
        }
        return _json(_foundResponse(place: 'Kitchen counter'));
      }),
    );

    expect(voice.started, isFalse);
    await tester.tap(find.byKey(const Key('voice-mic')));
    // The listening ripple animates continuously; pump once instead of settling.
    await tester.pump();
    expect(voice.started, isTrue);

    voice.emit('Where are my keys?');
    await tester.pumpAndSettle();

    expect(asked, 'keys');
    expect(find.text('Kitchen counter'), findsOneWidget);
  });

  testWidgets('call uses the number set during setup', (tester) async {
    final call = FakeCallService();
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      call: call,
      client: MockClient((_) async => _json({'found': false})),
    );

    await tester.tap(find.byKey(const Key('open-call')));
    await tester.pumpAndSettle();
    expect(find.text('Need a hand?'), findsOneWidget);
    expect(find.text('Sarah'), findsWidgets);

    await tester.tap(find.byKey(const Key('call-now')));
    await tester.pumpAndSettle();

    expect(call.calls, ['+1 555 010 2030']);
    expect(find.text('Calling Sarah...'), findsNothing);
    expect(find.byKey(const Key('call-status')), findsNothing);
    expect(find.text('Send Message'), findsOneWidget);
  });

  testWidgets('server address is editable without rebuilding (no USB needed)',
      (tester) async {
    final api = ApiService(
      baseUrl: 'http://test',
      client: MockClient((_) async => _json({'found': false})),
    );
    SharedPreferences.resetStatic();
    SharedPreferences.setMockInitialValues(_configuredPrefs);
    await tester.pumpWidget(AegisPatientApp(
      apiService: api,
      voiceService: NoVoiceService(),
      callService: FakeCallService(),
      preferencesService: PreferencesService(),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('open-server-settings')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('server-url-field')),
      'https://demo.example.modal.run',
    );
    await tester.tap(find.byKey(const Key('server-url-save')));
    await tester.pumpAndSettle();

    expect(api.baseUrl, 'https://demo.example.modal.run');
  });

  testWidgets('a saved server address is applied on startup', (tester) async {
    final api = ApiService(
      baseUrl: 'http://test',
      client: MockClient((_) async => _json({'found': false})),
    );
    SharedPreferences.resetStatic();
    SharedPreferences.setMockInitialValues({
      ..._configuredPrefs,
      'server_url': 'http://192.168.1.20:8000/',
    });
    await tester.pumpWidget(AegisPatientApp(
      apiService: api,
      voiceService: NoVoiceService(),
      callService: FakeCallService(),
      preferencesService: PreferencesService(),
    ));
    await tester.pumpAndSettle();

    expect(api.baseUrl, 'http://192.168.1.20:8000');
  });

  testWidgets('header shows LIVE when the server answers', (tester) async {
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/health') {
          return _json({'status': 'ok'});
        }
        return _json(_datasetsResponse(const []));
      }),
    );
    expect(find.text('LIVE'), findsOneWidget);
    expect(find.text('NOT LIVE'), findsNothing);
  });

  testWidgets('header shows NOT LIVE when the server is down', (tester) async {
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/health') {
          throw http.ClientException('offline');
        }
        return _json(_datasetsResponse(const []));
      }),
    );
    expect(find.text('NOT LIVE'), findsOneWidget);
    expect(find.text('LIVE'), findsNothing);
  });

  testWidgets('an unreachable server never claims "not in history"',
      (tester) async {
    tester.view.physicalSize = const Size(800, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await _pumpApp(
      tester,
      prefs: _configuredPrefs,
      client: MockClient((request) async {
        if (request.url.path == '/api/v1/datasets') {
          return _json(_datasetsResponse(['Keys #1']));
        }
        throw http.ClientException('offline');
      }),
    );

    await tester.tap(find.byKey(const Key('object-keys')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('unreachable-message')), findsOneWidget);
    expect(find.text(ApiService.notFoundMessage), findsNothing);
  });
}
