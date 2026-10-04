class TimelineEvent {
  final String eventId;
  final String eventType;
  final String object;
  final String? sourceRelation;
  final String? destinationRelation;
  final String? sourceAnchor;
  final String? destinationAnchor;
  final double startTime;
  final double endTime;
  final String summary;

  const TimelineEvent({
    required this.eventId,
    required this.eventType,
    required this.object,
    this.sourceRelation,
    this.destinationRelation,
    this.sourceAnchor,
    this.destinationAnchor,
    required this.startTime,
    required this.endTime,
    required this.summary,
  });

  factory TimelineEvent.fromJson(Map<String, dynamic> json) {
    return TimelineEvent(
      eventId: json['event_id'] as String? ?? '',
      eventType: json['event_type'] as String? ?? 'state_change',
      object: json['object'] as String? ?? 'Object',
      sourceRelation: json['source_relation'] as String?,
      destinationRelation: json['destination_relation'] as String?,
      sourceAnchor: json['source_anchor'] as String?,
      destinationAnchor: json['destination_anchor'] as String?,
      startTime: (json['start_time'] as num?)?.toDouble() ?? 0.0,
      endTime: (json['end_time'] as num?)?.toDouble() ?? 0.0,
      summary: json['summary'] as String? ?? '',
    );
  }
}

class SpatialAnchor {
  final int anchorId;
  final String label;
  final List<double> center;
  final List<double> size;
  final List<String> containedObjects;

  const SpatialAnchor({
    required this.anchorId,
    required this.label,
    required this.center,
    required this.size,
    required this.containedObjects,
  });

  factory SpatialAnchor.fromJson(Map<String, dynamic> json) {
    return SpatialAnchor(
      anchorId: json['anchor_id'] as int? ?? 0,
      label: json['label'] as String? ?? 'Anchor',
      center: (json['center'] as List<dynamic>?)?.map((e) => (e as num).toDouble()).toList() ?? [0, 0, 0],
      size: (json['size'] as List<dynamic>?)?.map((e) => (e as num).toDouble()).toList() ?? [1, 1, 1],
      containedObjects: (json['contained_objects'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
    );
  }
}
