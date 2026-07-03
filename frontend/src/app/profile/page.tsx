"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { getUser, logout, saveUser, User } from "@/lib/auth";
import { AppShell } from "@/components/AppShell";

const INDUSTRIES = [
  "Payment Gateway", "Banking", "E-commerce", "Fintech",
  "Insurance", "Cryptocurrency", "Other",
];

const COMPANY_SIZES = [
  "Startup (1-50)", "SMB (51-500)", "Mid-market (501-5000)", "Enterprise (5000+)",
];

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  // Profile edit
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileFullName, setProfileFullName] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSuccess, setProfileSuccess] = useState(false);

  // Password change
  const [changingPassword, setChangingPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  // Company edit
  const [editingCompany, setEditingCompany] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [companyIndustry, setCompanyIndustry] = useState(INDUSTRIES[0]);
  const [companySize, setCompanySize] = useState(COMPANY_SIZES[0]);
  const [companyUseCase, setCompanyUseCase] = useState("");
  const [companySaving, setCompanySaving] = useState(false);
  const [companyError, setCompanyError] = useState<string | null>(null);
  const [companySuccess, setCompanySuccess] = useState(false);

  useEffect(() => {
    const u = getUser();
    if (!u) {
      router.replace("/login");
      return;
    }
    setUser(u);
    setProfileFullName(u.full_name ?? "");
    if (u.company) {
      setCompanyName(u.company.name);
      setCompanyIndustry(u.company.industry ?? INDUSTRIES[0]);
      setCompanySize(u.company.size ?? COMPANY_SIZES[0]);
      setCompanyUseCase(u.company.use_case ?? "");
    }
  }, [router]);

  if (!user) return null;

  const isAdmin = user.role === "admin";

  async function saveProfile() {
    setProfileError(null);
    setProfileSaving(true);
    try {
      const updated = await api<User>("/api/profile", {
        method: "PATCH",
        body: { full_name: profileFullName.trim() || null },
      });
      saveUser(updated);
      setUser(updated);
      setEditingProfile(false);
      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 2500);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
        router.replace("/login");
        return;
      }
      setProfileError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setProfileSaving(false);
    }
  }

  async function savePassword() {
    setPasswordError(null);
    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }
    setPasswordSaving(true);
    try {
      await api<User>("/api/profile", {
        method: "PATCH",
        body: {
          current_password: currentPassword,
          new_password: newPassword,
        },
      });
      setChangingPassword(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordSuccess(true);
      setTimeout(() => setPasswordSuccess(false), 3000);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) setPasswordError("Current password is incorrect");
        else setPasswordError(err.message);
      } else {
        setPasswordError("Password change failed");
      }
    } finally {
      setPasswordSaving(false);
    }
  }

  async function saveCompany() {
    const currentUser = user;
    if (!currentUser) return;
    setCompanyError(null);
    setCompanySaving(true);
    try {
      const updated = await api<{ id: number; name: string; industry: string | null; size: string | null; use_case: string | null; logo_url: string | null }>(
        "/api/company",
        {
          method: "PATCH",
          body: {
            name: companyName.trim(),
            industry: companyIndustry,
            size: companySize,
            use_case: companyUseCase.trim() || null,
          },
        }
      );
      if (currentUser.company) {
        const nu: User = { ...currentUser, company: { ...currentUser.company, ...updated } };
        saveUser(nu);
        setUser(nu);
      }
      setEditingCompany(false);
      setCompanySuccess(true);
      setTimeout(() => setCompanySuccess(false), 2500);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 403) setCompanyError("Admin role required");
        else setCompanyError(err.message);
      } else {
        setCompanyError("Company update failed");
      }
    } finally {
      setCompanySaving(false);
    }
  }

  const userInitials = user.full_name
    ? user.full_name.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()
    : user.email.substring(0, 2).toUpperCase();

  const companyInitials = user.company?.name
    ? user.company.name.substring(0, 2).toUpperCase()
    : "CF";

  return (
    <AppShell title="Profile & Settings" subtitle="Manage your account and workspace">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 stagger">
        {/* Your Profile */}
        <section className="rounded-xl glass p-6">
          <div className="flex items-start justify-between mb-5">
            <div className="flex items-center gap-4">
              <div
                className="w-16 h-16 rounded-2xl accent-gradient flex items-center justify-center text-white font-black text-xl shadow-xl"
                style={{ boxShadow: "0 8px 24px -8px var(--accent-glow)" }}
              >
                {userInitials}
              </div>
              <div>
                <div className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--accent-primary)" }}>
                  Your profile
                </div>
                <div className="text-lg font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
                  {user.full_name ?? user.email.split("@")[0]}
                </div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                  {user.role.toUpperCase()} · {user.email}
                </div>
              </div>
            </div>
            {!editingProfile && (
              <button
                onClick={() => setEditingProfile(true)}
                className="text-xs font-medium px-3 py-1.5 rounded-lg transition glass glass-hover"
                style={{ color: "var(--text-secondary)" }}
              >
                Edit
              </button>
            )}
          </div>

          {profileSuccess && <SuccessBanner text="Profile updated" />}
          {profileError && <ErrorBanner text={profileError} />}

          <div className="space-y-3">
            <Field label="Full name">
              {editingProfile ? (
                <input
                  type="text"
                  value={profileFullName}
                  onChange={(e) => setProfileFullName(e.target.value)}
                  className={inputCls}
                  placeholder="Your name"
                />
              ) : (
                <div style={{ color: "var(--text-primary)" }} className="text-sm">
                  {user.full_name || <span style={{ color: "var(--text-faded)" }}>Not set</span>}
                </div>
              )}
            </Field>
            <Field label="Email"><div className="text-sm font-mono" style={{ color: "var(--text-primary)" }}>{user.email}</div></Field>
            <Field label="Role"><RolePill role={user.role} /></Field>
            <Field label="Status">
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: user.is_active ? "#34d399" : "#f87171" }} />
                <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                  {user.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            </Field>
          </div>

          {editingProfile && (
            <div className="flex gap-2 mt-5">
              <button
                onClick={() => { setEditingProfile(false); setProfileFullName(user.full_name ?? ""); setProfileError(null); }}
                className="px-4 h-9 rounded-lg text-sm font-medium glass glass-hover transition"
                style={{ color: "var(--text-muted)" }}
              >
                Cancel
              </button>
              <button
                onClick={saveProfile}
                disabled={profileSaving}
                className="px-4 h-9 rounded-lg text-sm font-semibold accent-gradient text-white disabled:opacity-60 transition hover:scale-105"
              >
                {profileSaving ? "Saving..." : "Save changes"}
              </button>
            </div>
          )}

          {/* Password change */}
          <div className="mt-6 pt-5" style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Password</div>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>Change your login password</div>
              </div>
              {!changingPassword && (
                <button
                  onClick={() => setChangingPassword(true)}
                  className="text-xs font-medium px-3 py-1.5 rounded-lg transition glass glass-hover"
                  style={{ color: "var(--text-secondary)" }}
                >
                  Change
                </button>
              )}
            </div>

            {passwordSuccess && <SuccessBanner text="Password changed successfully" />}
            {passwordError && <ErrorBanner text={passwordError} />}

            {changingPassword && (
              <div className="space-y-3">
                <Field label="Current password">
                  <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className={inputCls} />
                </Field>
                <Field label="New password (min 8 chars)">
                  <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className={inputCls} />
                </Field>
                <Field label="Confirm new password">
                  <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className={inputCls} />
                </Field>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => { setChangingPassword(false); setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); setPasswordError(null); }}
                    className="px-4 h-9 rounded-lg text-sm font-medium glass glass-hover transition"
                    style={{ color: "var(--text-muted)" }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={savePassword}
                    disabled={passwordSaving || !currentPassword || !newPassword}
                    className="px-4 h-9 rounded-lg text-sm font-semibold accent-gradient text-white disabled:opacity-60 transition hover:scale-105"
                  >
                    {passwordSaving ? "Updating..." : "Update password"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Company info */}
        <section className="rounded-xl glass p-6">
          <div className="flex items-start justify-between mb-5">
            <div className="flex items-center gap-4">
              <div
                className="w-16 h-16 rounded-2xl accent-gradient flex items-center justify-center text-white font-black text-xl shadow-xl"
                style={{ boxShadow: "0 8px 24px -8px var(--accent-glow)" }}
              >
                {companyInitials}
              </div>
              <div>
                <div className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--accent-primary)" }}>
                  Company workspace
                </div>
                <div className="text-lg font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-serif)" }}>
                  {user.company?.name ?? "No company"}
                </div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                  {user.company?.industry ?? "—"}
                </div>
              </div>
            </div>
            {isAdmin && !editingCompany && user.company && (
              <button
                onClick={() => setEditingCompany(true)}
                className="text-xs font-medium px-3 py-1.5 rounded-lg transition glass glass-hover"
                style={{ color: "var(--text-secondary)" }}
              >
                Edit
              </button>
            )}
          </div>

          {companySuccess && <SuccessBanner text="Company updated" />}
          {companyError && <ErrorBanner text={companyError} />}

          {user.company ? (
            <div className="space-y-3">
              <Field label="Company name">
                {editingCompany ? (
                  <input type="text" value={companyName} onChange={(e) => setCompanyName(e.target.value)} className={inputCls} />
                ) : (
                  <div className="text-sm" style={{ color: "var(--text-primary)" }}>{user.company.name}</div>
                )}
              </Field>

              <Field label="Industry">
                {editingCompany ? (
                  <select value={companyIndustry} onChange={(e) => setCompanyIndustry(e.target.value)} className={inputCls}>
                    {INDUSTRIES.map((i) => <option key={i} value={i}>{i}</option>)}
                  </select>
                ) : (
                  <div className="text-sm" style={{ color: "var(--text-primary)" }}>{user.company.industry ?? "—"}</div>
                )}
              </Field>

              <Field label="Size">
                {editingCompany ? (
                  <select value={companySize} onChange={(e) => setCompanySize(e.target.value)} className={inputCls}>
                    {COMPANY_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                ) : (
                  <div className="text-sm" style={{ color: "var(--text-primary)" }}>{user.company.size ?? "—"}</div>
                )}
              </Field>

              <Field label="Use case">
                {editingCompany ? (
                  <textarea rows={3} value={companyUseCase} onChange={(e) => setCompanyUseCase(e.target.value)} className={inputCls + " resize-none"} placeholder="What do you use fraud detection for?" />
                ) : (
                  <div className="text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>
                    {user.company.use_case || <span style={{ color: "var(--text-faded)" }}>Not set</span>}
                  </div>
                )}
              </Field>

              {!isAdmin && (
                <div className="mt-4 p-3 rounded-lg" style={{ background: "var(--bg-glass)", border: "1px solid var(--border-subtle)" }}>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Company details can only be edited by an admin.
                  </div>
                </div>
              )}

              {editingCompany && (
                <div className="flex gap-2 mt-5">
                  <button
                    onClick={() => { setEditingCompany(false); if (user.company) { setCompanyName(user.company.name); setCompanyIndustry(user.company.industry ?? INDUSTRIES[0]); setCompanySize(user.company.size ?? COMPANY_SIZES[0]); setCompanyUseCase(user.company.use_case ?? ""); } setCompanyError(null); }}
                    className="px-4 h-9 rounded-lg text-sm font-medium glass glass-hover transition"
                    style={{ color: "var(--text-muted)" }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={saveCompany}
                    disabled={companySaving}
                    className="px-4 h-9 rounded-lg text-sm font-semibold accent-gradient text-white disabled:opacity-60 transition hover:scale-105"
                  >
                    {companySaving ? "Saving..." : "Save changes"}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="p-4 text-sm text-center" style={{ color: "var(--text-muted)" }}>No company associated.</div>
          )}
        </section>
      </div>
    </AppShell>
  );
}

const inputCls = "w-full h-9 rounded-lg px-3 text-sm bg-transparent focus:outline-none transition";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest font-semibold mb-1" style={{ color: "var(--text-faded)" }}>{label}</div>
      <div style={{ background: "var(--bg-glass)", border: "1px solid var(--border-subtle)", borderRadius: "8px", padding: "8px 12px" }}>
        {children}
      </div>
    </div>
  );
}

function RolePill({ role }: { role: string }) {
  const isAdmin = role === "admin";
  return (
    <span
      className="inline-block px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
      style={{
        background: isAdmin ? "rgba(244,63,94,0.12)" : "var(--bg-glass)",
        color: isAdmin ? "var(--accent-primary)" : "var(--text-secondary)",
        border: `1px solid ${isAdmin ? "rgba(244,63,94,0.3)" : "var(--border-subtle)"}`,
      }}
    >
      {role}
    </span>
  );
}

function SuccessBanner({ text }: { text: string }) {
  return (
    <div
      className="mb-4 px-3 py-2 rounded-lg text-xs animate-fade-in"
      style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)", color: "#34d399" }}
    >
      ✓ {text}
    </div>
  );
}

function ErrorBanner({ text }: { text: string }) {
  return (
    <div
      className="mb-4 px-3 py-2 rounded-lg text-xs animate-fade-in"
      style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#f87171" }}
    >
      {text}
    </div>
  );
}
