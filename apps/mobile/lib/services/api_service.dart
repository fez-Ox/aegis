import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/dataset_info.dart';
import '../models/patient_search_record.dart';
import '../models/query_result.dart';
import '../models/timeline_event.dart';

class ApiService {
  String baseUrl;
  String? activeDatasetId;
  final http.Client _client;
  final List<PatientSearchRecord> _searchHistory = [];

  /// One timeout for every request.
  static const Duration requestTimeout = Duration(seconds: 5);

  /// Message shown when the memory server cannot be reached.
  static const String unreachableMessage =
      "Can't reach Aegis memory. Check the connection and try again.";

  /// Whether the server exposes the demo simulator (from /health).
  bool simulatorEnabled = false;

  /// Last connection error, or null after a successful request.
  String? lastError;

  ApiService({
    this.baseUrl = 'http://127.0.0.1:8000',
    this.activeDatasetId = 'demo01',
    http.Client? client,
  }) : _client = client ?? http.Client();

  String get _selectedDatasetId => activeDatasetId ?? 'demo01';

  /// Retrieve recent searches for the selected video only.
  List<PatientSearchRecord> getRecentSearches({int limit = 3}) {
    return _searchHistory
        .where((item) => item.datasetId == _selectedDatasetId)
        .take(limit)
        .toList();
  }

  /// Append a new search record to the selected video's history.
  void recordSearch(QueryResult result) {
    final datasetId = _selectedDatasetId;
    _searchHistory.removeWhere(
      (item) => item.datasetId == datasetId &&
          item.query.toLowerCase() == result.query.toLowerCase(),
    );
    _searchHistory.insert(
      0,
      PatientSearchRecord(
        datasetId: datasetId,
        query: result.query,
        found: result.found,
        instanceLabel: result.instanceLabel,
        anchorLabel: result.anchorLabel,
        locationSummary: result.locationSummary,
        timeAgo: 'Just now',
        timestamp: DateTime.now(),
        isPersistentMemory: result.isPersistentMemory,
      ),
    );
  }

  /// Dynamically update the backend host URL.
  ///
  /// Accepts either a complete URL or a bare LAN host such as
  /// `192.168.10.11`; the latter is normalized for the default API port.
  void updateBaseUrl(String newUrl) {
    String trimmed = newUrl.trim();
    if (trimmed.isEmpty) return;
    if (!trimmed.contains('://')) {
      trimmed = 'http://$trimmed';
    }
    final parsed = Uri.tryParse(trimmed);
    if (parsed != null && parsed.host.isNotEmpty && !parsed.hasPort) {
      trimmed = parsed.replace(port: 8000).toString();
    }
    while (trimmed.endsWith('/')) {
      trimmed = trimmed.substring(0, trimmed.length - 1);
    }
    baseUrl = trimmed;
  }


  /// Check server health and connectivity
  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/health');
      final response = await _client.get(uri).timeout(requestTimeout);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        activeDatasetId = data['dataset_loaded'] as String? ?? activeDatasetId;
        simulatorEnabled = data['simulator_enabled'] as bool? ?? false;
        lastError = null;
        return true;
      }
      return false;
    } catch (_) {
      lastError = unreachableMessage;
      return false;
    }
  }

  /// Fetch all available datasets discovered on the server.
  ///
  /// Returns an empty list when the server cannot be reached; the app never
  /// shows datasets it did not receive.
  Future<List<DatasetInfo>> fetchDatasets() async {
    final uri = Uri.parse('$baseUrl/api/v1/datasets');
    try {
      final response = await _client.get(uri).timeout(requestTimeout);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        activeDatasetId = data['active_dataset'] as String? ?? activeDatasetId;
        final list = data['available_datasets'] as List<dynamic>? ?? [];
        lastError = null;
        return list.map((item) => DatasetInfo.fromJson(item as Map<String, dynamic>)).toList();
      }
    } catch (_) {
      // Reported through lastError below.
    }
    lastError = unreachableMessage;
    return [];
  }

  /// Select active dataset on server
  Future<bool> selectDataset(String datasetId) async {
    activeDatasetId = datasetId;
    final uri = Uri.parse('$baseUrl/api/v1/dataset/select?dataset_id=${Uri.encodeComponent(datasetId)}');
    try {
      final response = await _client.post(uri).timeout(requestTimeout);
      return response.statusCode == 200;
    } catch (_) {
      lastError = unreachableMessage;
      return false;
    }
  }

  /// Trigger a demo state change (only when the server enables the simulator).
  Future<bool> simulatePreset(String preset) async {
    try {
      final queryParam = activeDatasetId != null ? '?dataset_id=$activeDatasetId' : '';
      final uri = Uri.parse('$baseUrl/api/v1/simulate/$preset$queryParam');
      final response = await _client.get(uri).timeout(requestTimeout);
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Drop simulated changes on the server.
  Future<bool> resetMemory() async {
    try {
      final queryParam = activeDatasetId != null ? '?dataset_id=$activeDatasetId' : '';
      final uri = Uri.parse('$baseUrl/api/v1/reset$queryParam');
      final response = await _client.post(uri).timeout(requestTimeout);
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Query location of a tracked item.
  ///
  /// When the server cannot be reached the result says so; it never contains
  /// a location the server did not send.
  Future<QueryResult> queryItem(String item) async {
    final queryParam = activeDatasetId != null ? '&dataset_id=$activeDatasetId' : '';
    final uri = Uri.parse('$baseUrl/api/v1/query?item=${Uri.encodeComponent(item)}$queryParam');
    try {
      final response = await _client.get(uri).timeout(requestTimeout);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        lastError = null;
        return QueryResult.fromJson(data);
      }
    } catch (_) {
      // Reported as an unreachable result below.
    }
    lastError = unreachableMessage;
    return QueryResult(
      query: item,
      found: false,
      locationSummary: unreachableMessage,
      unreachable: true,
    );
  }

  /// Fetch chronological timeline events for the caregiver view.
  Future<List<TimelineEvent>> fetchTimeline() async {
    final queryParam = activeDatasetId != null ? '?dataset_id=$activeDatasetId' : '';
    final uri = Uri.parse('$baseUrl/api/v1/timeline$queryParam');
    try {
      final response = await _client.get(uri).timeout(requestTimeout);
      if (response.statusCode == 200) {
        final list = jsonDecode(response.body) as List<dynamic>;
        lastError = null;
        return list.map((e) => TimelineEvent.fromJson(e as Map<String, dynamic>)).toList();
      }
    } catch (_) {
      // Reported through lastError below.
    }
    lastError = unreachableMessage;
    return [];
  }

  /// Live capture status (null when the server has no capture configured).
  Future<CaptureStatus?> fetchCaptureStatus() async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/capture/status');
      final response = await _client.get(uri).timeout(requestTimeout);
      if (response.statusCode == 200) {
        return CaptureStatus.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
      }
    } catch (_) {
      lastError = unreachableMessage;
    }
    return null;
  }

  /// Pause (true) or resume (false) the live capture.
  Future<CaptureStatus?> setCapturePaused(bool paused) async {
    try {
      final action = paused ? 'pause' : 'resume';
      final uri = Uri.parse('$baseUrl/api/v1/capture/$action');
      final response = await _client.post(uri).timeout(requestTimeout);
      if (response.statusCode == 200) {
        return CaptureStatus.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
      }
    } catch (_) {
      lastError = unreachableMessage;
    }
    return null;
  }
}

/// Live capture state reported by the server.
class CaptureStatus {
  final bool available;
  final bool paused;
  final String? sessionId;
  final String? status;
  final int? frameCount;

  const CaptureStatus({
    required this.available,
    required this.paused,
    this.sessionId,
    this.status,
    this.frameCount,
  });

  factory CaptureStatus.fromJson(Map<String, dynamic> json) {
    return CaptureStatus(
      available: json['available'] as bool? ?? false,
      paused: json['paused'] as bool? ?? false,
      sessionId: json['session_id'] as String?,
      status: json['status'] as String?,
      frameCount: json['frame_count'] as int?,
    );
  }
}
