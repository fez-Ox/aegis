import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/search_entry.dart';

/// Device-only search history. Entries keep tier and ambiguity so the
/// caregiver can filter to "the ones Aegis was unsure about".
class HistoryService {
  static const _key = 'caregiver_search_history';
  static const _max = 50;

  Future<List<SearchEntry>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return const [];
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! List) return const [];
      return decoded
          .whereType<Map>()
          .map((e) => SearchEntry.fromJson(Map<String, dynamic>.from(e)))
          .toList();
    } catch (_) {
      return const [];
    }
  }

  Future<List<SearchEntry>> add(SearchEntry entry) async {
    final entries = List<SearchEntry>.from(await load());
    entries.insert(0, entry);
    final trimmed = entries.take(_max).toList();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _key,
      jsonEncode(trimmed.map((e) => e.toJson()).toList()),
    );
    return trimmed;
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
