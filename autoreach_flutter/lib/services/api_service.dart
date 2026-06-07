import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/lead.dart';
import '../services/auth_service.dart';
import '../constants.dart';

const _base = kBaseUrl;

/// Central API service — all calls go to the live AutoReach backend.
class ApiService {
  static Future<Map<String, String>> _headers() async {
    final token = await AuthService.getToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  // ── Leads ──────────────────────────────────────────────────────────────────

  /// Fetch all unsent leads (have email, not yet contacted).
  static Future<List<Lead>> getLeads() async {
    final resp = await http.get(
      Uri.parse('$_base/api/leads'),
      headers: await _headers(),
    ).timeout(const Duration(seconds: 20));
    _checkAuth(resp);
    if (resp.statusCode != 200) throw Exception('Server error ${resp.statusCode}');
    final list = jsonDecode(resp.body) as List;
    return list.map((m) => Lead.fromApiMap(m as Map<String, dynamic>)).toList();
  }

  /// Fetch ALL leads (for the leads list screen).
  static Future<List<Lead>> getAllLeads() async {
    final resp = await http.get(
      Uri.parse('$_base/api/all-leads'),
      headers: await _headers(),
    ).timeout(const Duration(seconds: 20));
    _checkAuth(resp);
    if (resp.statusCode != 200) throw Exception('Server error ${resp.statusCode}');
    final list = jsonDecode(resp.body) as List;
    return list.map((m) => Lead.fromApiMap(m as Map<String, dynamic>)).toList();
  }

  /// Add a single lead.
  static Future<void> addLead(Lead lead) async {
    final resp = await http.post(
      Uri.parse('$_base/api/add-lead'),
      headers: await _headers(),
      body: jsonEncode({
        'name': lead.name,
        'address': lead.address,
        'phone': lead.phone,
        'website': lead.website,
        'email': lead.email,
        'notes': '',
      }),
    ).timeout(const Duration(seconds: 20));
    _checkAuth(resp);
    if (resp.statusCode != 200) {
      throw Exception('Failed to add lead: ${resp.statusCode}');
    }
  }

  /// Trigger server-side email scraping.
  static Future<void> triggerScrape() async {
    final resp = await http.post(
      Uri.parse('$_base/api/scrape'),
      headers: await _headers(),
    ).timeout(const Duration(seconds: 10));
    _checkAuth(resp);
  }

  /// Add multiple leads at once (from Google Maps find).
  static Future<int> addLeads(List<Lead> leads) async {
    int saved = 0;
    for (final lead in leads) {
      try {
        await addLead(lead);
        saved++;
      } catch (_) {}
    }
    return saved;
  }

  /// Update lead stage.
  static Future<void> updateLeadStage(String name, String stage) async {
    final resp = await http.post(
      Uri.parse('$_base/api/update-stage'),
      headers: await _headers(),
      body: jsonEncode({'name': name, 'stage': stage}),
    ).timeout(const Duration(seconds: 20));
    _checkAuth(resp);
  }

  // ── Stats ──────────────────────────────────────────────────────────────────

  static Future<Map<String, int>> getStats() async {
    final resp = await http.get(
      Uri.parse('$_base/api/stats'),
      headers: await _headers(),
    ).timeout(const Duration(seconds: 20));
    _checkAuth(resp);
    if (resp.statusCode != 200) throw Exception('Server error ${resp.statusCode}');
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    return data.map((k, v) => MapEntry(k, (v as num).toInt()));
  }

  // ── Sent log ───────────────────────────────────────────────────────────────

  static Future<List<Map<String, dynamic>>> getSentEmails() async {
    final resp = await http.get(
      Uri.parse('$_base/api/sent'),
      headers: await _headers(),
    ).timeout(const Duration(seconds: 20));
    _checkAuth(resp);
    if (resp.statusCode != 200) throw Exception('Server error ${resp.statusCode}');
    final list = jsonDecode(resp.body) as List;
    return list.cast<Map<String, dynamic>>();
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  static void _checkAuth(http.Response resp) {
    if (resp.statusCode == 401 || resp.statusCode == 302) {
      // Clear the stale token so the app redirects to login on next startup
      AuthService.clearToken();
      throw Exception('Session expired. Please log in again.');
    }
  }
}
