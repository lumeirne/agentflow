"use client";

import { useState, useEffect } from "react";
import { apiGet, apiPost } from "@/lib/auth";

interface SettingsData {
  id?: string;
  user_id?: string;
  default_slack_channel: string;
  working_hours_start: string;
  working_hours_end: string;
  timezone: string;
  default_meeting_duration_mins: number;
  fallback_team_json: string | null;
}

const DEFAULT_SETTINGS: SettingsData = {
  default_slack_channel: "",
  working_hours_start: "09:00",
  working_hours_end: "17:00",
  timezone: "UTC",
  default_meeting_duration_mins: 30,
  fallback_team_json: null,
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData>(DEFAULT_SETTINGS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const data = await apiGet<SettingsData>("/api/settings");
        setSettings(data);
      } catch {
        // Use defaults
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await apiPost("/api/settings", {
        default_slack_channel: settings.default_slack_channel || null,
        working_hours_start: settings.working_hours_start,
        working_hours_end: settings.working_hours_end,
        timezone: settings.timezone,
        default_meeting_duration_mins: settings.default_meeting_duration_mins,
        fallback_team_json: settings.fallback_team_json,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error("Failed to save settings:", err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
        <p className="text-gray-400">
          Configure default preferences for your AgentFlow workflows.
        </p>
      </div>

      <div className="space-y-6 rounded-2xl border border-white/5 bg-gray-900/50 p-6">
        {/* Slack Channel */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">
            Default Slack Channel
          </label>
          <input
            type="text"
            value={settings.default_slack_channel || ""}
            onChange={(e) => setSettings({ ...settings, default_slack_channel: e.target.value })}
            placeholder="#engineering"
            className="w-full px-4 py-2.5 rounded-xl bg-gray-800 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 transition-colors"
          />
        </div>

        {/* Meeting Duration */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">
            Default Meeting Duration (minutes)
          </label>
          <select
            value={settings.default_meeting_duration_mins}
            onChange={(e) => setSettings({ ...settings, default_meeting_duration_mins: Number(e.target.value) })}
            className="w-full px-4 py-2.5 rounded-xl bg-gray-800 border border-white/10 text-white focus:outline-none focus:border-blue-500/50 transition-colors"
          >
            <option value={15}>15 minutes</option>
            <option value={30}>30 minutes</option>
            <option value={45}>45 minutes</option>
            <option value={60}>60 minutes</option>
            <option value={90}>90 minutes</option>
          </select>
        </div>

        {/* Working Hours */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Working Hours Start
            </label>
            <input
              type="time"
              value={settings.working_hours_start}
              onChange={(e) => setSettings({ ...settings, working_hours_start: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl bg-gray-800 border border-white/10 text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              Working Hours End
            </label>
            <input
              type="time"
              value={settings.working_hours_end}
              onChange={(e) => setSettings({ ...settings, working_hours_end: e.target.value })}
              className="w-full px-4 py-2.5 rounded-xl bg-gray-800 border border-white-/10 text-white focus:outline-none focus:border-blue-500/50 transition-colors"
            />
          </div>
        </div>

        {/* Timezone */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">
            Timezone
          </label>
          <select
            value={settings.timezone}
            onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
            className="w-full px-4 py-2.5 rounded-xl bg-gray-800 border border-white/10 text-white focus:outline-none focus:border-blue-500/50 transition-colors"
          >
            <option value="UTC">UTC</option>
            <option value="America/New_York">America/New York (EST)</option>
            <option value="America/Chicago">America/Chicago (CST)</option>
            <option value="America/Denver">America/Denver (MST)</option>
            <option value="America/Los_Angeles">America/Los Angeles (PST)</option>
            <option value="Europe/London">Europe/London (GMT)</option>
            <option value="Europe/Berlin">Europe/Berlin (CET)</option>
            <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
            <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
            <option value="Australia/Sydney">Australia/Sydney (AEST)</option>
          </select>
        </div>

        {/* Save Button */}
        <div className="flex items-center gap-4 pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-medium text-sm transition-all duration-300 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
          {saved && (
            <span className="text-sm text-emerald-400 animate-pulse">✓ Saved successfully</span>
          )}
        </div>
      </div>
    </div>
  );
}
