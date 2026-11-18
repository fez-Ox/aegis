import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:aegis_mobile/main.dart';
import 'package:aegis_mobile/services/api_service.dart';

http.Response _json(Map<String, dynamic> body) => http.Response(
      jsonEncode(body),
      200,
      headers: {'content-type': 'application/json'},
    );

void main() {
  testWidgets('shows the grounded answer from /ask', (tester) async {
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/ask');
      return _json({
        'question': 'where are my keys',
        'intent': 'locate',
        'status': 'answered',
        'answer': 'Your keys are inside Storage Cabinet #1 in the Room #1.',
        'found': true,
        'abstained': false,
        'anchor_label': 'Storage Cabinet #1',
        'room_label': 'Room #1',
        'evidence': [
          {'crop_url': '/api/v1/crops/1?dataset_id=demo01'}
        ],
      });
    });
    await tester.pumpWidget(
      AegisApp(apiService: ApiService(baseUrl: 'http://test', client: client)),
    );
    await tester.enterText(find.byKey(const Key('ask-field')), 'where are my keys');
    await tester.tap(find.byKey(const Key('ask-send')));
    await tester.pumpAndSettle();

    expect(find.textContaining('Storage Cabinet #1'), findsWidgets);
    expect(find.text('ANSWER'), findsOneWidget);
  });

  testWidgets('shows an honest abstention', (tester) async {
    final client = MockClient((request) async => _json({
          'answer': "I haven't seen your teleporter.",
          'abstained': true,
          'abstain_reason': 'item_not_in_dictionary',
          'evidence': [],
        }));
    await tester.pumpWidget(
      AegisApp(apiService: ApiService(baseUrl: 'http://test', client: client)),
    );
    await tester.enterText(find.byKey(const Key('ask-field')), 'where is my teleporter');
    await tester.tap(find.byKey(const Key('ask-send')));
    await tester.pumpAndSettle();
    expect(find.textContaining('teleporter'), findsOneWidget);
    expect(find.text('NOT SURE'), findsOneWidget);
  });

  testWidgets('unreachable server shows no location', (tester) async {
    final client = MockClient((request) async => throw http.ClientException('offline'));
    await tester.pumpWidget(
      AegisApp(apiService: ApiService(baseUrl: 'http://test', client: client)),
    );
    await tester.enterText(find.byKey(const Key('ask-field')), 'where are my keys');
    await tester.tap(find.byKey(const Key('ask-send')));
    await tester.pumpAndSettle();
    expect(find.textContaining("Can't reach Aegis memory"), findsOneWidget);
    expect(find.textContaining('Storage Cabinet'), findsNothing);
  });
}
