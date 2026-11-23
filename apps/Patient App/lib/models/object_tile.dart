/// The quick-tap object cards from the patient mockup.
///
/// These are *prompts*, not claims that the object exists in memory. Tapping a
/// tile asks Aegis; if there is no history the drawer says so plainly.
enum ObjectKind {
  keys,
  glasses,
  phone,
  wallet,
  medicine,
  remote,
  mug,
  shoe,
  book,
  bottle,
  laptop,
  chair,
  other,
}

class ObjectTile {
  final String label;
  final ObjectKind kind;
  final String question;

  const ObjectTile({
    required this.label,
    required this.kind,
    required this.question,
  });

  /// Build a tile from a server label such as "Cell Phone #4".
  factory ObjectTile.fromServerLabel(String raw) {
    final name = raw.replaceFirst(RegExp(r'\s*#\d+.*$'), '').trim();
    final lower = name.toLowerCase();
    final kind = switch (lower) {
      'cell phone' || 'phone' => ObjectKind.phone,
      'book' => ObjectKind.book,
      'bottle' || 'water bottle' => ObjectKind.bottle,
      'laptop' => ObjectKind.laptop,
      'chair' => ObjectKind.chair,
      'keys' => ObjectKind.keys,
      'glasses' => ObjectKind.glasses,
      'wallet' => ObjectKind.wallet,
      'medicine' => ObjectKind.medicine,
      'mug' => ObjectKind.mug,
      'shoes' => ObjectKind.shoe,
      _ => ObjectKind.other,
    };
    final display = name.isEmpty ? raw : name;
    return ObjectTile(
      label: display,
      kind: kind,
      question: 'Where is my $lower?',
    );
  }

  // Tiles are built only from objects the server actually remembers.

}
