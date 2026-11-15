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
  final String? lastSeenAt;
  final String? lastSeenTimeAgo;
  final bool isPersistentMemory;
  final String? cropUrl;
  final double? confidence;
  final String? roomLabel;

  /// True when the server could not be reached (no memory was consulted).
  final bool unreachable;

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
    this.lastSeenAt,
    this.lastSeenTimeAgo,
    this.isPersistentMemory = false,
    this.cropUrl,
    this.confidence,
    this.roomLabel,
    this.unreachable = false,
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
      lastSeenAt: json['last_seen_at'] as String?,
      lastSeenTimeAgo: json['last_seen_time_ago'] as String?,
      isPersistentMemory: json['is_persistent_memory'] as bool? ?? false,
      cropUrl: json['crop_url'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      roomLabel: json['room_label'] as String?,
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
      'last_seen_at': lastSeenAt,
      'last_seen_time_ago': lastSeenTimeAgo,
      'is_persistent_memory': isPersistentMemory,
      'crop_url': cropUrl,
      'confidence': confidence,
      'room_label': roomLabel,
    };
  }
}
