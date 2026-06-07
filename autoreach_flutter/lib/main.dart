import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'services/auth_service.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/leads_screen.dart';
import 'screens/add_lead_screen.dart';
import 'screens/find_leads_screen.dart';
import 'screens/outreach_screen.dart';
import 'screens/sent_screen.dart';
import 'screens/report_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/aria_screen.dart';

final _navigatorKey = GlobalKey<NavigatorState>();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // First do a fast local JWT expiry check, then verify with the server
  // (server check runs async so startup isn't blocked if offline)
  final localOk = await AuthService.isLoggedIn();
  bool loggedIn = localOk;
  if (localOk) {
    loggedIn = await AuthService.verifyWithServer();
  }
  runApp(AutoReachApp(loggedIn: loggedIn));
}

class AutoReachApp extends StatefulWidget {
  final bool loggedIn;
  const AutoReachApp({super.key, required this.loggedIn});
  @override
  State<AutoReachApp> createState() => _AutoReachAppState();
}

class _AutoReachAppState extends State<AutoReachApp> {
  late final AppLinks _appLinks;

  @override
  void initState() {
    super.initState();
    _initDeepLinks();
  }

  /// Handle autoreach://callback?token=JWT coming back from OAuth.
  void _initDeepLinks() {
    _appLinks = AppLinks();
    _appLinks.uriLinkStream.listen((uri) async {
      if (uri.scheme == 'autoreach' && uri.host == 'callback') {
        final token = uri.queryParameters['token'];
        final error = uri.queryParameters['error'];
        if (token != null) {
          await AuthService.saveToken(token);
          _navigatorKey.currentState?.pushReplacementNamed('/');
        } else if (error != null) {
          // Show error on the login screen via snackbar
          _navigatorKey.currentState?.pushReplacementNamed('/login');
          ScaffoldMessenger.of(_navigatorKey.currentContext!).showSnackBar(
            SnackBar(
              content: Text('Login failed: $error'),
              backgroundColor: const Color(0xFFFF6B6B),
            ),
          );
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AutoReach',
      navigatorKey: _navigatorKey,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF6C63FF),
          secondary: Color(0xFF4ECDC4),
          surface: Color(0xFF1E1E2E),
          background: Color(0xFF141421),
          onPrimary: Colors.white,
          onSurface: Color(0xFFCDD6F4),
        ),
        scaffoldBackgroundColor: const Color(0xFF141421),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF1E1E2E),
          foregroundColor: Color(0xFFCDD6F4),
          elevation: 0,
        ),
        cardTheme: const CardThemeData(
          color: Color(0xFF1E1E2E),
          elevation: 2,
          margin: EdgeInsets.symmetric(vertical: 6, horizontal: 0),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFF2A2A3E),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF444466))),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF444466))),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF6C63FF))),
          labelStyle: const TextStyle(color: Color(0xFF888AAA)),
          hintStyle: const TextStyle(color: Color(0xFF555577)),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF6C63FF),
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
          ),
        ),
        useMaterial3: true,
      ),
      initialRoute: widget.loggedIn ? '/' : '/login',
      routes: {
        '/login':      (context) => const LoginScreen(),
        '/':           (context) => const DashboardScreen(),
        '/leads':      (context) => const LeadsScreen(),
        '/add_lead':   (context) => const AddLeadScreen(),
        '/find_leads': (context) => const FindLeadsScreen(),
        '/outreach':   (context) => const OutreachScreen(),
        '/sent':       (context) => const SentScreen(),
        '/report':     (context) => const ReportScreen(),
        '/settings':   (context) => const SettingsScreen(),
        '/aria':       (context) => const AriaScreen(),
      },
    );
  }
}
