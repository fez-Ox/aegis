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
  bool _backendAvailable = false;

  ApiService({
    this.baseUrl = 'http://127.0.0.1:8000',
    this.activeDatasetId = 'demo01',
    http.Client? client,
  }) : _client = client ?? http.Client() {
    _seedInitialSearchHistory();
  }

  void _seedInitialSearchHistory() {
    // Seed only memories belonging to the initial dataset.  These records are
    // filtered again at read time, so switching to another video cannot show
    // objects from this demonstration.
    final now = DateTime.now();
    const datasetId = 'demo01';
    _searchHistory.addAll([
      PatientSearchRecord(
        datasetId: datasetId,
        query: 'shoes',
        found: true,
        instanceLabel: 'Shoes #1 [Active Pair]',
        anchorLabel: 'Storage Cabinet #1',
        locationSummary: 'Inside Storage Cabinet #1, bottom shelf near entrance.',
        timeAgo: '25m ago',
        timestamp: now.subtract(const Duration(minutes: 25)),
        isPersistentMemory: true,
      ),
    ]);
  }

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
    _backendAvailable = false;
    while (trimmed.endsWith('/')) {
      trimmed = trimmed.substring(0, trimmed.length - 1);
    }
    baseUrl = trimmed;
  }

  /// Check server health and connectivity
  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/api/v1/health');
      final response = await _client.get(uri).timeout(const Duration(seconds: 2));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        activeDatasetId = data['dataset_loaded'] as String? ?? activeDatasetId;
        _backendAvailable = true;
        return true;
      }
      _backendAvailable = false;
      return false;
    } catch (_) {
      _backendAvailable = false;
      return false;
    }
  }

  /// Fetch all available datasets discovered on the server
  Future<List<DatasetInfo>> fetchDatasets() async {
    if (!_backendAvailable) return _offlineDatasetCatalog();

    final uri = Uri.parse('$baseUrl/api/v1/datasets');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        activeDatasetId = data['active_dataset'] as String? ?? activeDatasetId;
        final list = data['available_datasets'] as List<dynamic>? ?? [];
        return list.map((item) => DatasetInfo.fromJson(item as Map<String, dynamic>)).toList();
      }
    } catch (_) {
      // Offline fallback dataset list
    }
    return _offlineDatasetCatalog();
  }

  List<DatasetInfo> _offlineDatasetCatalog() {
    return [
      const DatasetInfo(
        datasetId: 'demo04',
        title: 'Empty The Trash',
        anchors: ['Storage Cabinet #1'],
        trackedObjects: [
          'Garbage Bag #1',
          'Garbage Bag #4',
          'Food Container #2',
          'Plastic Bottle #3',
          'Rubbish #5',
        ],
        numEvents: 5,
        numTimelineFrames: 117,
        isActive: false,
      ),
      const DatasetInfo(
        datasetId: 'demo03',
        title: 'Put Leftover Food Into The Fridge Compartment',
        anchors: ['Refrigerator #1', 'Sink #2'],
        trackedObjects: ['Cooking Pot #1', 'Cooking Pot #16', 'Bowl #3', 'Bowl #12'],
        numEvents: 40,
        numTimelineFrames: 100,
        isActive: true,
      ),
      const DatasetInfo(
        datasetId: 'demo01',
        title: 'Put Shoes Into Storage Cabinet',
        anchors: ['Storage Cabinet #1'],
        trackedObjects: ['Shoes #1 [Active Pair]', 'Shoes #2', 'Shoes #3', 'Shoes #4'],
        numEvents: 3,
        numTimelineFrames: 108,
      ),
      const DatasetInfo(
        datasetId: 'Demo06-Self',
        title: 'Bottle Relocation Between Desks',
        anchors: ['Desk #1', 'Desk #2'],
        trackedObjects: ['Bottle #1', 'Cell Phone #3', 'Laptop #2'],
        numEvents: 1,
        numTimelineFrames: 24,
      ),
    ];
  }

  /// Select active dataset on server
  Future<bool> selectDataset(String datasetId) async {
    activeDatasetId = datasetId;
    if (!_backendAvailable) return true;

    final uri = Uri.parse('$baseUrl/api/v1/dataset/select?dataset_id=${Uri.encodeComponent(datasetId)}');
    try {
      final response = await _client.post(uri).timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) return true;
      _backendAvailable = false;
      return false;
    } catch (_) {
      _backendAvailable = false;
      return true; // Still update client-side active selection
    }
  }

  /// Trigger dynamic spatial state simulation
  Future<bool> simulatePreset(String preset) async {
    try {
      final queryParam = activeDatasetId != null ? '?dataset_id=$activeDatasetId' : '';
      final uri = Uri.parse('$baseUrl/api/v1/simulate/$preset$queryParam');
      final response = await _client.get(uri).timeout(const Duration(seconds: 3));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Reset memory cache to baseline
  Future<bool> resetMemory() async {
    try {
      final queryParam = activeDatasetId != null ? '?dataset_id=$activeDatasetId' : '';
      final uri = Uri.parse('$baseUrl/api/v1/reset$queryParam');
      final response = await _client.post(uri).timeout(const Duration(seconds: 3));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  bool get _useBundledSceneGraph =>
      !_backendAvailable && (_selectedDatasetId == 'demo04' || _selectedDatasetId == 'Demo06-Self');

  /// Query location of a tracked item
  Future<QueryResult> queryItem(String item) async {
    if (_useBundledSceneGraph) return _offlineQueryFallback(item);

    final queryParam = activeDatasetId != null ? '&dataset_id=$activeDatasetId' : '';
    final uri = Uri.parse('$baseUrl/api/v1/query?item=${Uri.encodeComponent(item)}$queryParam');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        _backendAvailable = true;
        return QueryResult.fromJson(data);
      }
    } catch (_) {
      // Offline fallback for seamless demo continuity
    }
    return _mockQueryFallback(item);
  }

  /// Fetch chronological timeline events for caregiver audit
  Future<List<TimelineEvent>> fetchTimeline() async {
    if (_useBundledSceneGraph) return _offlineTimelineFallback();

    final queryParam = activeDatasetId != null ? '?dataset_id=$activeDatasetId' : '';
    final uri = Uri.parse('$baseUrl/api/v1/timeline$queryParam');
    try {
      final response = await _client.get(uri).timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        final list = jsonDecode(response.body) as List<dynamic>;
        _backendAvailable = true;
        return list.map((e) => TimelineEvent.fromJson(e as Map<String, dynamic>)).toList();
      }
    } catch (_) {
      // Offline fallback
    }
    return _mockTimelineFallback();
  }

  QueryResult _offlineQueryFallback(String item) {
    final lower = item.trim().toLowerCase();
    final datasetId = _selectedDatasetId;

    if (datasetId == 'demo04') {
      if (lower.contains('food') || lower.contains('container')) {
        return const QueryResult(
          query: 'food container',
          found: true,
          item: 'food container',
          instanceLabel: 'Food Container #2',
          instanceId: 2,
          anchorLabel: 'Storage Cabinet #1',
          relation: 'inside',
          relativeDistanceM: 0.10,
          locationSummary: 'Your food is safely put away inside Storage Cabinet #1. Even though it is currently out of direct view behind the closed compartment, Aegis remembers it is securely stored inside.',
          lastSeenTimestampS: 7.217503,
          lastSeenTimeAgo: 'Recorded today',
          isPersistentMemory: true,
          cropUrl: '/api/v1/crops/2?dataset_id=demo04',
          confidence: 0.96,
        );
      }
      if (lower.contains('garbage') || lower.contains('trash')) {
        final isFourthBag = lower.contains('#4') || lower.contains('fourth');
        return QueryResult(
          query: item,
          found: true,
          item: 'garbage bag',
          instanceLabel: isFourthBag ? 'Garbage Bag #4' : 'Garbage Bag #1',
          instanceId: isFourthBag ? 4 : 1,
          anchorLabel: 'Storage Cabinet #1',
          relation: 'moving_towards',
          relativeDistanceM: isFourthBag ? 0.92 : 1.65,
          locationSummary: 'Your trash is near Storage Cabinet #1.',
          lastSeenTimestampS: isFourthBag ? 34.817771 : 42.402832,
          lastSeenTimeAgo: 'Recorded today',
          isPersistentMemory: true,
          cropUrl: '/api/v1/crops/${isFourthBag ? 4 : 1}?dataset_id=demo04',
          confidence: 0.96,
        );
      }
      if (lower.contains('rubbish')) {
        return const QueryResult(
          query: 'rubbish',
          found: true,
          item: 'rubbish',
          instanceLabel: 'Rubbish #5',
          instanceId: 5,
          anchorLabel: 'Storage Cabinet #1',
          relation: 'moving_towards',
          relativeDistanceM: 2.40,
          locationSummary: 'Your trash is near Storage Cabinet #1.',
          lastSeenTimestampS: 39.62944,
          lastSeenTimeAgo: 'Recorded today',
          isPersistentMemory: true,
          cropUrl: '/api/v1/crops/5?dataset_id=demo04',
          confidence: 0.96,
        );
      }
      if (lower.contains('bottle')) {
        return const QueryResult(
          query: 'plastic bottle',
          found: true,
          item: 'plastic bottle',
          instanceLabel: 'Plastic Bottle #3',
          instanceId: 3,
          anchorLabel: 'Storage Cabinet #1',
          relation: 'on_surface',
          relativeDistanceM: 0.50,
          locationSummary: 'Your bottle is currently resting on Storage Cabinet #1.',
          lastSeenTimestampS: 24.425903,
          lastSeenTimeAgo: 'Recorded today',
          cropUrl: '/api/v1/crops/3?dataset_id=demo04',
          confidence: 0.96,
        );
      }
      return QueryResult(
        query: item,
        found: false,
        locationSummary: "I couldn't locate any '$item' in demo04. Available items: Garbage Bag #1, Garbage Bag #4, Food Container #2, Plastic Bottle #3, Rubbish #5.",
      );
    }

    if (datasetId == 'Demo06-Self') {
      if (lower.contains('laptop') || lower.contains('computer')) {
        return const QueryResult(
          query: 'laptop',
          found: true,
          item: 'laptop',
          instanceLabel: 'Laptop #2',
          instanceId: 2,
          anchorLabel: 'Desk #2',
          relation: 'on_surface',
          relativeDistanceM: 0.30,
          locationSummary: 'Your laptop is sitting on Desk #2. Even though it is currently out of direct view, Aegis remembers it remains safely on Desk #2.',
          lastSeenTimestampS: 7.224284,
          lastSeenTimeAgo: 'Recorded today',
          isPersistentMemory: true,
          cropUrl: '/api/v1/crops/2?dataset_id=Demo06-Self',
          confidence: 0.96,
        );
      }
      if (lower.contains('phone') || lower.contains('mobile')) {
        return const QueryResult(
          query: 'cell phone',
          found: true,
          item: 'cell phone',
          instanceLabel: 'Cell Phone #3',
          instanceId: 3,
          anchorLabel: 'Desk #2',
          relation: 'on_surface',
          relativeDistanceM: 0.21,
          locationSummary: 'Your phone is sitting on Desk #2. Even though it is currently out of direct view, Aegis remembers it remains safely on Desk #2.',
          lastSeenTimestampS: 7.224284,
          lastSeenTimeAgo: 'Recorded today',
          isPersistentMemory: true,
          cropUrl: '/api/v1/crops/3?dataset_id=Demo06-Self',
          confidence: 0.96,
        );
      }
      if (lower.contains('bottle') || lower.contains('water') || lower.contains('drink')) {
        return const QueryResult(
          query: 'water bottle',
          found: true,
          item: 'water bottle',
          instanceLabel: 'Bottle #1',
          instanceId: 1,
          anchorLabel: 'Desk #2',
          relation: 'on_surface',
          relativeDistanceM: 0.07,
          locationSummary: 'Your bottle is currently resting on Desk #2.',
          lastSeenTimestampS: 9.231029,
          lastSeenTimeAgo: 'Recorded today',
          cropUrl: '/api/v1/crops/1?dataset_id=Demo06-Self',
          confidence: 0.96,
        );
      }
      return QueryResult(
        query: item,
        found: false,
        locationSummary: "I couldn't locate any '$item' in Demo06-Self. Available items: Bottle #1, Cell Phone #3, Laptop #2.",
      );
    }

    return QueryResult(
      query: item,
      found: false,
      locationSummary: 'The scene graph for $datasetId is not available yet.',
    );
  }

  /// Offline fallback simulating verified R4DSG memory across different datasets
  QueryResult _mockQueryFallback(String item) {
    final lower = item.toLowerCase();
    final datasetId = _selectedDatasetId;
    // Offline data is still dataset-scoped.  Unknown/unprocessed videos must
    // not receive a plausible result from another demonstration.
    if (datasetId == 'demo04' || datasetId == 'Demo06-Self') {
      return _offlineQueryFallback(item);
    }
    if (datasetId != 'demo01' && datasetId != 'demo03') {
      return QueryResult(
        query: item,
        found: false,
        locationSummary: 'The scene graph for $datasetId is not available yet.',
      );
    }
    if (lower.contains('pot') || lower.contains('pan') || lower.contains('cookware')) {
      return const QueryResult(
        query: 'cooking pot',
        found: true,
        item: 'cooking pot',
        instanceLabel: 'Cooking Pot #16',
        instanceId: 16,
        anchorLabel: 'Refrigerator #1',
        relation: 'on_surface',
        relativeDistanceM: 0.31,
        locationSummary: 'Your cooking pot is currently resting on Refrigerator #1.',
        lastSeenTimeAgo: 'Recorded today',
        isPersistentMemory: false,
        cropUrl: '/api/v1/crops/16?dataset_id=demo03',
        confidence: 0.96,
      );
    } else if (lower.contains('bowl') || lower.contains('dish')) {
      return const QueryResult(
        query: 'bowl',
        found: true,
        item: 'bowl',
        instanceLabel: 'Bowl #12',
        instanceId: 12,
        anchorLabel: 'Refrigerator #1',
        relation: 'inside',
        relativeDistanceM: 0.08,
        locationSummary: 'Your bowl is safely stored inside Refrigerator #1.',
        lastSeenTimeAgo: 'Recorded today',
        isPersistentMemory: true,
        cropUrl: '/api/v1/crops/12?dataset_id=demo03',
        confidence: 0.95,
      );
    } else if (lower.contains('bottle') || lower.contains('water') || lower.contains('drink')) {
      return const QueryResult(
        query: 'water bottle',
        found: true,
        item: 'water bottle',
        instanceLabel: 'Bottle #1',
        instanceId: 1,
        anchorLabel: 'Desk #2',
        relation: 'on_surface',
        relativeDistanceM: 0.07,
        locationSummary: 'Your bottle is currently resting on Desk #2.',
        lastSeenTimeAgo: 'Recorded today',
        isPersistentMemory: false,
        cropUrl: '/api/v1/crops/1?dataset_id=Demo06-Self',
        confidence: 0.96,
      );
    } else if (lower.contains('shoe')) {
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

  List<TimelineEvent> _offlineTimelineFallback() {
    if (_selectedDatasetId == 'demo04') {
      return const [
        TimelineEvent(
          eventId: 'event_0001',
          eventType: 'placement',
          object: 'Garbage Bag #1',
          sourceRelation: 'carried_by_user',
          destinationRelation: 'inside',
          sourceAnchor: 'Storage Cabinet #1',
          destinationAnchor: 'Storage Cabinet #1',
          startTime: 31.609992,
          endTime: 32.010964,
          summary: 'Garbage Bag #1 was placed inside Storage Cabinet #1.',
        ),
        TimelineEvent(
          eventId: 'event_0002',
          eventType: 'state_change',
          object: 'Garbage Bag #1',
          sourceRelation: 'inside',
          destinationRelation: 'on_surface',
          sourceAnchor: 'Storage Cabinet #1',
          destinationAnchor: 'Storage Cabinet #1',
          startTime: 34.015826,
          endTime: 34.416798,
          summary: 'Garbage Bag #1 is resting on Storage Cabinet #1.',
        ),
        TimelineEvent(
          eventId: 'event_0003',
          eventType: 'state_change',
          object: 'Garbage Bag #1',
          sourceRelation: 'on_surface',
          destinationRelation: 'moving_towards',
          sourceAnchor: 'Storage Cabinet #1',
          destinationAnchor: 'Storage Cabinet #1',
          startTime: 34.416798,
          endTime: 34.817771,
          summary: 'Garbage Bag #1 transition from on_surface to moving_towards.',
        ),
        TimelineEvent(
          eventId: 'event_0004',
          eventType: 'placement',
          object: 'Food Container #2',
          sourceRelation: 'carried_by_user',
          destinationRelation: 'inside',
          sourceAnchor: 'Storage Cabinet #1',
          destinationAnchor: 'Storage Cabinet #1',
          startTime: 31.609992,
          endTime: 32.010964,
          summary: 'Food Container #2 was placed inside Storage Cabinet #1.',
        ),
        TimelineEvent(
          eventId: 'event_0005',
          eventType: 'state_change',
          object: 'Rubbish #5',
          sourceRelation: 'on_surface',
          destinationRelation: 'moving_towards',
          sourceAnchor: 'Storage Cabinet #1',
          destinationAnchor: 'Storage Cabinet #1',
          startTime: 39.228467,
          endTime: 39.62944,
          summary: 'Rubbish #5 transition from on_surface to moving_towards.',
        ),
      ];
    }
    if (_selectedDatasetId == 'Demo06-Self') {
      return const [
        TimelineEvent(
          eventId: 'event_0001',
          eventType: 'anchor_change',
          object: 'Bottle #1',
          sourceRelation: 'on_surface',
          destinationRelation: 'on_surface',
          sourceAnchor: 'Desk #1',
          destinationAnchor: 'Desk #2',
          startTime: 7.625633,
          endTime: 8.026982,
          summary: 'Bottle #1 was moved from Desk #1 to Desk #2.',
        ),
      ];
    }
    return const [];
  }

  List<TimelineEvent> _mockTimelineFallback() {
    if (_selectedDatasetId == 'demo04' || _selectedDatasetId == 'Demo06-Self') {
      return _offlineTimelineFallback();
    }
    if (activeDatasetId == 'demo03') {
      return const [
        TimelineEvent(
          eventId: 'ev_001',
          eventType: 'state_change',
          object: 'Cooking Pot #1',
          sourceRelation: 'on_surface',
          destinationRelation: 'moving_towards',
          destinationAnchor: 'Sink #2',
          startTime: 1.0,
          endTime: 2.0,
          summary: 'Cooking Pot #1 transition from on_surface to moving_towards.',
        ),
        TimelineEvent(
          eventId: 'ev_002',
          eventType: 'placement',
          object: 'Cooking Pot #16',
          destinationRelation: 'on_surface',
          destinationAnchor: 'Refrigerator #1',
          startTime: 88.0,
          endTime: 91.0,
          summary: 'Cooking Pot #16 is resting on Refrigerator #1.',
        ),
        TimelineEvent(
          eventId: 'ev_003',
          eventType: 'state_change',
          object: 'Bowl #12',
          sourceRelation: 'on_surface',
          destinationRelation: 'inside',
          destinationAnchor: 'Refrigerator #1',
          startTime: 75.0,
          endTime: 80.0,
          summary: 'Bowl #12 was placed inside Refrigerator #1.',
        ),
      ];
    }
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
