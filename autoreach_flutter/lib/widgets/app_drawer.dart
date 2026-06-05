import 'package:flutter/material.dart';
import '../services/auth_service.dart';

class AppDrawer extends StatelessWidget {
  const AppDrawer({super.key});

  @override
  Widget build(BuildContext context) {
    final route = ModalRoute.of(context)?.settings.name ?? '/';
    return Drawer(
      backgroundColor: const Color(0xFF1A1A2E),
      child: SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.all(24),
              child: Column(children: [
                Icon(Icons.rocket_launch, color: Color(0xFF6C63FF), size: 40),
                SizedBox(height: 8),
                Text('AutoReach', style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
                Text('Lead & Outreach Tool', style: TextStyle(color: Color(0xFF888AAA), fontSize: 12)),
              ]),
            ),
            const Divider(color: Color(0xFF2A2A3E)),
            _Item(icon: Icons.dashboard,       label: 'Dashboard',   route: '/',           current: route),
            _Item(icon: Icons.people,           label: 'Leads',       route: '/leads',      current: route),
            _Item(icon: Icons.search,           label: 'Find Leads',  route: '/find_leads', current: route),
            _Item(icon: Icons.send,             label: 'Outreach',    route: '/outreach',   current: route),
            _Item(icon: Icons.mark_email_read,  label: 'Sent',        route: '/sent',       current: route),
            _Item(icon: Icons.bar_chart,        label: 'Report',      route: '/report',     current: route),
            _Item(icon: Icons.smart_toy,        label: 'ARIA',        route: '/aria',       current: route, accent: const Color(0xFF4ECDC4)),
            const Spacer(),
            const Divider(color: Color(0xFF2A2A3E)),
            _Item(icon: Icons.settings,         label: 'Settings',    route: '/settings',   current: route),
            _LogoutButton(),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }
}

class _Item extends StatelessWidget {
  final IconData icon; final String label, route, current;
  final Color? accent;
  const _Item({required this.icon, required this.label, required this.route, required this.current, this.accent});

  @override
  Widget build(BuildContext context) {
    final selected = current == route;
    final color = accent ?? const Color(0xFF6C63FF);
    return ListTile(
      leading: Icon(icon, color: selected ? color : const Color(0xFF888AAA), size: 20),
      title: Text(label, style: TextStyle(color: selected ? color : const Color(0xFFCDD6F4), fontWeight: selected ? FontWeight.bold : FontWeight.normal, fontSize: 14)),
      tileColor: selected ? color.withOpacity(0.1) : null,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      onTap: () { Navigator.pop(context); if (!selected) Navigator.pushReplacementNamed(context, route); },
    );
  }
}

class _LogoutButton extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.logout, color: Color(0xFFFF6B6B), size: 20),
      title: const Text('Log Out', style: TextStyle(color: Color(0xFFFF6B6B), fontSize: 14)),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      onTap: () async {
        await AuthService.clearToken();
        if (context.mounted) Navigator.pushReplacementNamed(context, '/login');
      },
    );
  }
}
