import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/lead.dart';
import 'settings_service.dart';

class MapsService {
  static Future<List<Lead>> findBusinesses(String city, String businessType) async {
    final apiKey = await SettingsService.getGoogleApiKey();
    if (apiKey.isEmpty) throw Exception('Google API key not set. Go to Settings.');
    final results = <Lead>[];
    String? pageToken;
    do {
      final params = pageToken != null
          ? {'pagetoken': pageToken, 'key': apiKey}
          : {'query': '$businessType in $city', 'key': apiKey};
      final uri = Uri.parse('https://maps.googleapis.com/maps/api/place/textsearch/json').replace(queryParameters: params);
      final response = await http.get(uri).timeout(const Duration(seconds: 15));
      final data = jsonDecode(response.body);
      for (final place in data['results'] ?? []) {
        final details = await _details(place['place_id'], apiKey);
        results.add(Lead(name: place['name'] ?? '', address: place['formatted_address'] ?? '', phone: details['phone'] ?? '', website: details['website'] ?? '', email: ''));
      }
      pageToken = data['next_page_token'];
      if (pageToken != null) await Future.delayed(const Duration(seconds: 2));
    } while (pageToken != null);
    return results;
  }

  static Future<Map<String, String>> _details(String placeId, String apiKey) async {
    final uri = Uri.parse('https://maps.googleapis.com/maps/api/place/details/json').replace(queryParameters: {'place_id': placeId, 'fields': 'formatted_phone_number,website', 'key': apiKey});
    final data = jsonDecode((await http.get(uri).timeout(const Duration(seconds: 10))).body)['result'] ?? {};
    return {'phone': data['formatted_phone_number'] ?? '', 'website': data['website'] ?? ''};
  }
}
