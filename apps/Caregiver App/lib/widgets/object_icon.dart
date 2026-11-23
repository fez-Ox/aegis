import 'package:flutter/material.dart';

import '../models/object_tile.dart';

/// Line-style icons mirroring the inline SVGs in patient.html. Material icons
/// keep the app dependency-free while staying legible at large touch sizes.
IconData iconFor(ObjectKind kind) => switch (kind) {
      ObjectKind.keys => Icons.vpn_key_outlined,
      ObjectKind.glasses => Icons.visibility_outlined,
      ObjectKind.phone => Icons.smartphone_outlined,
      ObjectKind.wallet => Icons.account_balance_wallet_outlined,
      ObjectKind.medicine => Icons.medication_outlined,
      ObjectKind.remote => Icons.settings_remote_outlined,
      ObjectKind.mug => Icons.local_cafe_outlined,
      ObjectKind.shoe => Icons.directions_walk_outlined,
      ObjectKind.book => Icons.menu_book_outlined,
      ObjectKind.bottle => Icons.local_drink_outlined,
      ObjectKind.laptop => Icons.laptop_outlined,
      ObjectKind.chair => Icons.event_seat_outlined,
      ObjectKind.other => Icons.help_outline,
    };

/// A deterministic warm gradient so each object gets a stable "photo" tone,
/// matching the mockup's tone-indexed placeholder images.
List<Color> toneFor(ObjectKind kind) {
  const tones = [
    [Color(0xFF4A3D29), Color(0xFF2A2318)],
    [Color(0xFF5A4A33), Color(0xFF221C13)],
    [Color(0xFF3B3426), Color(0xFF2E281C)],
  ];
  return tones[kind.index % tones.length];
}
