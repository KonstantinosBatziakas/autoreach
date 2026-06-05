import 'package:http/http.dart' as http;

class ScraperService {
  static final _emailRegex = RegExp(r'[\w\.\-]+@[\w\.\-]+\.\w+', caseSensitive: false);
  static final _skipExts = ['.png','.jpg','.css','.js','.svg'];

  static Future<String> findEmailForBusiness(String website) async {
    if (website.isEmpty) return '';
    final base = website.endsWith('/') ? website.substring(0, website.length - 1) : website;
    String email = await _findOnPage(base);
    if (email.isNotEmpty) return email;
    for (final path in ['/contact','/contact-us','/about','/about-us']) {
      await Future.delayed(const Duration(seconds: 1));
      email = await _findOnPage('$base$path');
      if (email.isNotEmpty) return email;
    }
    return '';
  }

  static Future<String> _findOnPage(String url) async {
    try {
      final res = await http.get(Uri.parse(url), headers: {'User-Agent': 'Mozilla/5.0 AutoReach/1.0'}).timeout(const Duration(seconds: 8));
      return _emailRegex.allMatches(res.body).map((m) => m.group(0)!).where((e) => !_skipExts.any((x) => e.endsWith(x))).firstOrNull ?? '';
    } catch (_) { return ''; }
  }
}
