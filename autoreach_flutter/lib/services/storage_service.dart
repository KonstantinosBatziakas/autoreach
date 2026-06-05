import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:csv/csv.dart';
import '../models/lead.dart';
import '../models/sent_email.dart';

class StorageService {
  static Future<String> get _localPath async => (await getApplicationDocumentsDirectory()).path;
  static Future<File> _file(String name) async => File('${await _localPath}/$name');

  // ── LEADS ──
  static Future<List<Lead>> getLeads() async {
    try {
      final f = await _file('businesses.csv');
      if (!await f.exists()) return [];
      final rows = const CsvToListConverter().convert(await f.readAsString(), eol: '\n');
      if (rows.isEmpty) return [];
      final headers = rows.first.map((e) => e.toString()).toList();
      return rows.skip(1).map((row) {
        final map = <String, String>{};
        for (int i = 0; i < headers.length; i++) map[headers[i]] = i < row.length ? row[i].toString() : '';
        return Lead.fromMap(map);
      }).toList();
    } catch (_) { return []; }
  }

  static Future<void> saveLeads(List<Lead> leads) async {
    final f = await _file('businesses.csv');
    final rows = [
      ['name','address','phone','website','email','stage'],
      ...leads.map((l) => [l.name, l.address, l.phone, l.website, l.email, l.stage]),
    ];
    await f.writeAsString(const ListToCsvConverter().convert(rows));
  }

  static Future<void> addLead(Lead lead) async {
    final leads = await getLeads();
    leads.add(lead);
    await saveLeads(leads);
  }

  static Future<void> updateLeadEmail(String name, String email) async {
    final leads = await getLeads();
    final idx = leads.indexWhere((l) => l.name == name);
    if (idx != -1) { leads[idx] = leads[idx].copyWith(email: email); await saveLeads(leads); }
  }

  static Future<void> updateLeadStage(String name, String stage) async {
    final leads = await getLeads();
    final idx = leads.indexWhere((l) => l.name == name);
    if (idx != -1) { leads[idx] = leads[idx].copyWith(stage: stage); await saveLeads(leads); }
  }

  static Future<String> exportLeadsCsv() async {
    final leads = await getLeads();
    final rows = [
      ['name','address','phone','website','email','stage'],
      ...leads.map((l) => [l.name, l.address, l.phone, l.website, l.email, l.stage]),
    ];
    return const ListToCsvConverter().convert(rows);
  }

  // ── SENT LOG ──
  static Future<List<SentEmail>> getSentEmails() async {
    try {
      final f = await _file('sent_log.csv');
      if (!await f.exists()) return [];
      final rows = const CsvToListConverter().convert(await f.readAsString(), eol: '\n');
      if (rows.isEmpty) return [];
      final headers = rows.first.map((e) => e.toString()).toList();
      return rows.skip(1).map((row) {
        final map = <String, String>{};
        for (int i = 0; i < headers.length; i++) map[headers[i]] = i < row.length ? row[i].toString() : '';
        return SentEmail.fromMap(map);
      }).toList();
    } catch (_) { return []; }
  }

  static Future<void> logSentEmail(SentEmail sent) async {
    final f = await _file('sent_log.csv');
    final bool exists = await f.exists();
    List<List<dynamic>> rows = exists
        ? const CsvToListConverter().convert(await f.readAsString(), eol: '\n')
        : [['business_name','email','subject','date_sent']];
    rows.add([sent.businessName, sent.email, sent.subject, sent.dateSent]);
    await f.writeAsString(const ListToCsvConverter().convert(rows));
  }
}
