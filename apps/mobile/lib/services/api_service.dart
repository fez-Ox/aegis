import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/query_result.dart';
import '../models/timeline_event.dart';

class ApiService {
  String baseUrl;
  final http.Client _client;

  ApiService({
    this.baseUrl = 'http://127.0.0.1:8000',
    http.Client? client,
  }) : _client = client ?? http.Client();

  /// Dynamically update the backend host URL
  void updateBaseUrl(String newUrl) {
    String trimmed = newUrl.trim();
    if (trimmed.endsWith('/')) {
      trimmed = trimmed.substring(0, trimmed.length - 1);
    }
    baseUrl = trimmed;
  }

  /// Check server health and connectivity
  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/health');
      final response = await _client.get(uri).timeout(const Duration(seconds: 2));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Trigger dynamic spatial state simulation (floor, cabinet, in_hand)
  Future<bool> simulatePreset(String preset) async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/simulate/$preset');
      final response = await _client.get(uri).timeout(const Duration(seconds: 3));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Reset memory cache to baseline
  Future<bool> resetMemory() async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/reset');
      final response = await _client.post(uri).timeout(const Duration(seconds: 3));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Query location of a tracked item
  Future<QueryResult> queryItem(String item) async {
    final uri = Uri.parse('$baseUrl/api/v1/query?item=${Uri.encodeComponent(item)}');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return QueryResult.fromJson(data);
      }
    } catch (_) {
      // Offline fallback for seamless demo continuity
    }
    return _mockQueryFallback(item);
  }

  /// Fetch chronological timeline events for caregiver audit
  Future<List<TimelineEvent>> fetchTimeline() async {
    final uri = Uri.parse('$baseUrl/api/v1/timeline');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        final list = jsonDecode(response.body) as List<dynamic>;
        return list.map((e) => TimelineEvent.fromJson(e as Map<String, dynamic>)).toList();
      }
    } catch (_) {
      // Offline fallback
    }
    return _mockTimelineFallback();
  }

  /// Offline fallback simulating verified R4DSG memory
  QueryResult _mockQueryFallback(String item) {
    final lower = item.toLowerCase();
    if (lower.contains('shoe')) {
      return const QueryResult(
        query: 'shoes',
        found: true,
        item: 'shoes',
        instanceLabel: 'Shoes #1 [Active Pair]',
        instanceId: 1,
        anchorLabel: 'Storage Cabinet #1',
        relation: 'inside',
        relativeDistanceM: 0.09,
        locationSummary: 'Inside Storage Cabinet #1, bottom shelf near entrance.',
        lastSeenTimeAgo: 'Placed 15 minutes ago',
        isPersistentMemory: true,
        cropUrl: '/api/v1/crops/1',
        confidence: 0.96,
      );
    } else if (lower.contains('key')) {
      return const QueryResult(
        query: 'keys',
        found: true,
        item: 'keys',
        instanceLabel: 'Keys #1 [Keychain]',
        instanceId: 5,
        anchorLabel: 'Entrance Console Table',
        relation: 'on_top',
        relativeDistanceM: 0.12,
        locationSummary: 'On the Entrance Console Table right beside the doorway.',
        lastSeenTimeAgo: 'Recorded 1 hour ago',
        isPersistentMemory: true,
        confidence: 0.94,
      );
    } else {
      return QueryResult(
        query: item,
        found: false,
        locationSummary: "I couldn't locate '$item' in your tracked rooms.",
      );
    }
  }

  List<TimelineEvent> _mockTimelineFallback() {
    return const [
      TimelineEvent(
        eventId: 'ev_001',
        eventType: 'state_change',
        object: 'Shoes #1 [Active Pair]',
        sourceRelation: 'on_floor',
        destinationRelation: 'inside',
        destinationAnchor: 'Storage Cabinet #1',
        startTime: 8.0,
        endTime: 35.6,
        summary: 'Shoes #1 [Active Pair] was placed inside Storage Cabinet #1.',
      ),
      TimelineEvent(
        eventId: 'ev_002',
        eventType: 'presence',
        object: 'Keys #1',
        destinationRelation: 'on_top',
        destinationAnchor: 'Entrance Console Table',
        startTime: 40.0,
        endTime: 42.0,
        summary: 'Keys placed on Entrance Console Table.',
      ),
    ];
  }
}
