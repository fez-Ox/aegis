class QueryResult {
  final String query;
  final bool found;
  final String? item;
  final String? instanceLabel;
  final int? instanceId;
  final String? anchorLabel;
  final String? relation;
  final double? relativeDistanceM;
  final String locationSummary;
  final double? lastSeenTimestampS;
  final String lastSeenTimeAgo;
  final bool isPersistentMemory;
  final String? cropUrl;
  final double confidence;

  const QueryResult({
    required this.query,
    required this.found,
    this.item,
    this.instanceLabel,
    this.instanceId,
    this.anchorLabel,
    this.relation,
    this.relativeDistanceM,
    required this.locationSummary,
    this.lastSeenTimestampS,
    this.lastSeenTimeAgo = 'Today',
    this.isPersistentMemory = false,
    this.cropUrl,
    this.confidence = 0.95,
  });

  factory QueryResult.fromJson(Map<String, dynamic> json) {
    return QueryResult(
      query: json['query'] as String? ?? '',
      found: json['found'] as bool? ?? false,
      item: json['item'] as String?,
      instanceLabel: json['instance_label'] as String?,
      instanceId: json['instance_id'] as int?,
      anchorLabel: json['anchor_label'] as String?,
      relation: json['relation'] as String?,
      relativeDistanceM: (json['relative_distance_m'] as num?)?.toDouble(),
      locationSummary: json['location_summary'] as String? ?? 'Object location unknown.',
      lastSeenTimestampS: (json['last_seen_timestamp_s'] as num?)?.toDouble(),
      lastSeenTimeAgo: json['last_seen_time_ago'] as String? ?? 'Recently',
      isPersistentMemory: json['is_persistent_memory'] as bool? ?? false,
      cropUrl: json['crop_url'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.95,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'query': query,
      'found': found,
      'item': item,
      'instance_label': instanceLabel,
      'instance_id': instanceId,
      'anchor_label': anchorLabel,
      'relation': relation,
      'relative_distance_m': relativeDistanceM,
      'location_summary': locationSummary,
      'last_seen_timestamp_s': lastSeenTimestampS,
      'last_seen_time_ago': lastSeenTimeAgo,
      'is_persistent_memory': isPersistentMemory,
      'crop_url': cropUrl,
      'confidence': confidence,
    };
  }
}
