import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

import '../constants.dart';
import '../services/auth_service.dart';
import '../services/settings_service.dart';

class ModerationQueueScreen extends StatefulWidget {
  const ModerationQueueScreen({super.key});

  @override
  State<ModerationQueueScreen> createState() => _ModerationQueueScreenState();
}

class _ModerationQueueScreenState extends State<ModerationQueueScreen> {
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _items = [];
  final Map<String, TextEditingController> _subjects = {};
  final Map<String, TextEditingController> _bodies = {};
  final Set<String> _submitting = {};

  @override
  void initState() {
    super.initState();
    _loadQueue();
  }

  @override
  void dispose() {
    for (final controller in [..._subjects.values, ..._bodies.values]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _loadQueue() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final token = await AuthService.getToken();
      if (token == null) throw Exception('Sign in to view moderation items.');
      final response = await http.get(
        Uri.parse('$kBaseUrl/api/moderation/queue'),
        headers: {'Authorization': 'Bearer $token'},
      ).timeout(const Duration(seconds: 15));
      final result = jsonDecode(response.body);
      if (response.statusCode != 200) {
        throw Exception(result['error'] ?? 'Could not load moderation items.');
      }
      final items = (result as List).cast<Map<String, dynamic>>();
      for (final item in items) {
        final id = item['id'] as String;
        final payload = item['payload'] as Map<String, dynamic>? ?? {};
        _subjects.putIfAbsent(
            id, () => TextEditingController(text: payload['subject'] ?? ''));
        _bodies.putIfAbsent(
            id,
            () => TextEditingController(
                text: payload['body'] ?? payload['content'] ?? ''));
      }
      if (!mounted) return;
      setState(() => _items = items);
    } catch (error) {
      if (mounted)
        setState(
            () => _error = error.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _resubmit(Map<String, dynamic> item) async {
    final id = item['id'] as String;
    setState(() => _submitting.add(id));
    try {
      final token = await AuthService.getToken();
      final content = _bodies[id]!.text.trim();
      final response = await http
          .post(
            Uri.parse('$kBaseUrl/api/moderation/queue/$id/resubmit'),
            headers: {
              'Content-Type': 'application/json',
              if (token != null) 'Authorization': 'Bearer $token',
            },
            body: jsonEncode({
              'subject': _subjects[id]!.text.trim(),
              'body': content,
              'content': content,
            }),
          )
          .timeout(const Duration(seconds: 20));
      final result = jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode != 200 && response.statusCode != 202) {
        throw Exception(result['error'] ?? 'Resubmission failed.');
      }
      if (result['status'] == 'saved' &&
          item['content_type'] == 'aria_prompt') {
        await SettingsService.setAriaCustomPrompt(content);
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(result['error'] ??
            switch (result['status']) {
              'sent' => 'Email sent after moderation.',
              'saved' => 'Content accepted and saved.',
              _ => 'Content queued for another check.',
            }),
      ));
      await _loadQueue();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(error.toString().replaceFirst('Exception: ', '')),
          backgroundColor: Colors.red.shade700,
        ));
      }
    } finally {
      if (mounted) setState(() => _submitting.remove(id));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Moderation Queue'),
          actions: [
            IconButton(
                tooltip: 'Acceptable Use Policy',
                onPressed: () =>
                    launchUrl(Uri.parse('$kBaseUrl/acceptable-use')),
                icon: const Icon(Icons.policy_outlined)),
            IconButton(onPressed: _loadQueue, icon: const Icon(Icons.refresh))
          ],
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? Center(child: Text(_error!))
                : _items.isEmpty
                    ? const Center(
                        child: Text('Nothing is waiting for moderation.'))
                    : ListView.builder(
                        padding: const EdgeInsets.all(16),
                        itemCount: _items.length,
                        itemBuilder: (context, index) {
                          final item = _items[index];
                          final id = item['id'] as String;
                          final isEmail = ['email', 'email_followup']
                              .contains(item['content_type']);
                          final isRetry = item['status'] == 'retry';
                          return Card(
                            margin: const EdgeInsets.only(bottom: 16),
                            child: Padding(
                              padding: const EdgeInsets.all(16),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                      '${item['content_type']} · ${item['status']}',
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleMedium),
                                  const SizedBox(height: 8),
                                  Text(isRetry
                                      ? 'The moderation provider is unavailable. The server will retry before sending.'
                                      : 'Edit the content and submit it for a fresh check. Email resubmission sends if it passes.'),
                                  if (isEmail) ...[
                                    const SizedBox(height: 12),
                                    TextField(
                                        controller: _subjects[id],
                                        decoration: const InputDecoration(
                                            labelText: 'Subject')),
                                  ],
                                  const SizedBox(height: 8),
                                  TextField(
                                    controller: _bodies[id],
                                    minLines: 4,
                                    maxLines: 10,
                                    decoration: const InputDecoration(
                                        labelText: 'Content'),
                                  ),
                                  const SizedBox(height: 12),
                                  FilledButton(
                                    onPressed:
                                        isRetry || _submitting.contains(id)
                                            ? null
                                            : () => _resubmit(item),
                                    child: Text(_submitting.contains(id)
                                        ? 'Checking…'
                                        : 'Edit and resubmit'),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
      );
}
