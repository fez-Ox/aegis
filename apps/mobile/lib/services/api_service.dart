import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/ask_result.dart';

/// Thin HTTP client: the app sends a question and receives an answer.
/// It does no reconstruction, tracking, promotion or memory mutation.
class ApiService {
  static const requestTimeout = Duration(seconds: 5);
  static const unreachableMessage =
      "Can't reach Aegis memory. Check the connection and try again.";

  final String baseUrl;
  final http.Client _client;

  ApiService({String? baseUrl, http.Client? client})
      : baseUrl = (baseUrl ?? 'http://127.0.0.1:8000').replaceAll(RegExp(r'/+$'), ''),
        _client = client ?? http.Client();

  /// Ask the deployed Aegis (Modal or local) memory one question.
  /// Returns `null` when the server cannot be reached — never an invented answer.
  Future<AskResult?> ask(String text) async {
    if (text.trim().isEmpty) return null;
    try {
      final uri = Uri.parse('$baseUrl/api/v1/ask')
          .replace(queryParameters: {'text': text.trim()});
      final response = await _client.get(uri).timeout(requestTimeout);
      if (response.statusCode != 200) return null;
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return AskResult.fromJson(data);
    } catch (_) {
      return null;
    }
  }

  String evidenceUrl(String path) =>
      path.startsWith('http') ? path : '$baseUrl$path';
}
