import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Save, Eye, EyeOff, LogOut, CheckCircle2, XCircle,
  Loader2, Clock, Terminal, Copy, Check, User, Wifi,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/shared/PageHeader";
import { useSessionStore } from "@/stores/session";
import { getHealth } from "@/lib/api/endpoints";

// ── Helpers ───────────────────────────────────────────────────────────────────
function getTokenExpiry(token: string): { daysLeft: number; expired: boolean } | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const raw = parts[1] ?? "";
    const padded = raw.padEnd(raw.length + ((4 - (raw.length % 4)) % 4), "=");
    const decoded = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    const obj = JSON.parse(decoded) as Record<string, unknown>;
    const exp = obj["exp"];
    if (typeof exp !== "number") return null;
    const msLeft = exp * 1000 - Date.now();
    return { daysLeft: Math.floor(msLeft / 86_400_000), expired: msLeft <= 0 };
  } catch {
    return null;
  }
}

// ── Schema ────────────────────────────────────────────────────────────────────
const schema = z.object({
  apiBaseUrl:  z.string().url("Must be a valid URL"),
  bearerToken: z.string().min(1, "Bearer token is required"),
});
type FormData = z.infer<typeof schema>;

// ── Copy button ───────────────────────────────────────────────────────────────
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="text-muted-foreground hover:text-foreground transition-colors p-0.5"
      aria-label="Copy to clipboard"
    >
      {copied
        ? <Check className="h-3.5 w-3.5 text-green-600" />
        : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

// ── Info row ──────────────────────────────────────────────────────────────────
function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-border last:border-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`text-xs font-medium text-foreground truncate max-w-[200px] ${mono ? "font-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function SettingsPage() {
  const {
    apiBaseUrl, bearerToken, claims, isAuthenticated,
    setApiBaseUrl, setBearerToken, clearSession,
  } = useSessionStore();

  const [showToken, setShowToken] = useState(false);
  const [testStatus, setTestStatus] = useState<"idle" | "loading" | "ok" | "fail">("idle");

  const { register, handleSubmit, formState: { errors, isDirty } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { apiBaseUrl, bearerToken },
  });

  const onSubmit = (data: FormData) => {
    setApiBaseUrl(data.apiBaseUrl);
    setBearerToken(data.bearerToken);
    toast.success("Settings saved");
  };

  const testConnection = async () => {
    setTestStatus("loading");
    try {
      await getHealth();
      setTestStatus("ok");
      toast.success("Backend is reachable");
    } catch {
      setTestStatus("fail");
      toast.error("Could not reach backend");
    } finally {
      setTimeout(() => setTestStatus("idle"), 4000);
    }
  };

  const expiry = bearerToken ? getTokenExpiry(bearerToken) : null;

  return (
    <div className="flex flex-col h-full">
      <PageHeader title="Settings" description="API connection and authentication" />

      <div className="flex-1 overflow-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 max-w-4xl">

          {/* ── Left column ──────────────────────────────────────────────── */}
          <div className="space-y-5">

          {/* ── Auth status ──────────────────────────────────────────────── */}
          <Card className="border-border shadow-none">
            <CardHeader className="pb-3 border-b border-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Auth Status
                  </CardTitle>
                </div>
                {isAuthenticated ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 border border-green-100 px-2.5 py-1 text-[11px] font-medium text-green-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                    Authenticated
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary border border-border px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                    <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
                    Not authenticated
                  </span>
                )}
              </div>
            </CardHeader>

            <CardContent className="pt-1 pb-3">
              {claims ? (
                <div>
                  <InfoRow label="Merchant ID" value={claims.merchant_id} mono />
                  <InfoRow label="Email"       value={claims.email} />
                  <InfoRow label="Role"        value={claims.role} />
                  <div className="flex items-center justify-between py-2.5">
                    <p className="text-xs text-muted-foreground">Token Expiry</p>
                    {expiry ? (
                      <p className={`text-xs font-medium flex items-center gap-1 ${
                        expiry.expired        ? "text-red-500"
                        : expiry.daysLeft < 7 ? "text-amber-600"
                        :                       "text-green-600"
                      }`}>
                        <Clock className="h-3 w-3" />
                        {expiry.expired
                          ? "Expired"
                          : expiry.daysLeft === 0
                            ? "Expires today"
                            : `${expiry.daysLeft} days left`}
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground">No expiry set</p>
                    )}
                  </div>
                </div>
              ) : (
                <p className="py-3 text-xs text-muted-foreground">
                  Paste a bearer token in the form below to authenticate.
                </p>
              )}
            </CardContent>
          </Card>

          {/* ── Connection form ───────────────────────────────────────────── */}
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <Card className="border-border shadow-none">
              <CardHeader className="pb-3 border-b border-border">
                <div className="flex items-center gap-2">
                  <Wifi className="h-4 w-4 text-muted-foreground" />
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Connection
                  </CardTitle>
                </div>
              </CardHeader>

              <CardContent className="pt-5 space-y-4">
                {/* API URL */}
                <div className="space-y-1.5">
                  <label htmlFor="apiBaseUrl" className="text-xs font-medium text-foreground">
                    Backend URL
                  </label>
                  <div className="flex gap-2">
                    <Input
                      id="apiBaseUrl"
                      type="url"
                      placeholder="https://your-api.onrender.com"
                      className="flex-1 text-sm"
                      {...register("apiBaseUrl")}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="shrink-0 h-9 px-3 text-xs gap-1.5"
                      onClick={testConnection}
                      disabled={testStatus === "loading"}
                    >
                      {testStatus === "loading" ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : testStatus === "ok" ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
                      ) : testStatus === "fail" ? (
                        <XCircle className="h-3.5 w-3.5 text-red-500" />
                      ) : null}
                      {testStatus === "idle"    ? "Test"
                      : testStatus === "loading" ? "Testing…"
                      : testStatus === "ok"      ? "Online"
                      :                            "Offline"}
                    </Button>
                  </div>
                  {errors.apiBaseUrl && (
                    <p className="text-xs text-destructive">{errors.apiBaseUrl.message}</p>
                  )}
                </div>

                {/* Bearer token */}
                <div className="space-y-1.5">
                  <label htmlFor="bearerToken" className="text-xs font-medium text-foreground">
                    Bearer Token
                  </label>
                  <div className="relative">
                    <Input
                      id="bearerToken"
                      type={showToken ? "text" : "password"}
                      placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…"
                      className="pr-9 font-mono text-xs"
                      {...register("bearerToken")}
                    />
                    <button
                      type="button"
                      onClick={() => setShowToken((v) => !v)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={showToken ? "Hide token" : "Show token"}
                    >
                      {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                  {errors.bearerToken && (
                    <p className="text-xs text-destructive">{errors.bearerToken.message}</p>
                  )}
                </div>

                <Separator />

                {/* Actions */}
                <div className="flex items-center justify-between">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => { clearSession(); toast.success("Session cleared"); }}
                    className="gap-1.5 text-xs text-muted-foreground hover:text-destructive px-0"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    Clear session
                  </Button>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!isDirty}
                    className="gap-1.5 text-xs"
                  >
                    <Save className="h-3.5 w-3.5" />
                    Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          </form>

          </div>{/* end left column */}

          {/* ── Right column — Token guide ────────────────────────────────── */}
          <Card className="border-border shadow-none self-start">
            <CardHeader className="pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Get a Token
                </CardTitle>
              </div>
            </CardHeader>

            <CardContent className="pt-4 space-y-4">
              {/* Production */}
              <div className="space-y-2">
                <p className="text-xs font-semibold text-foreground">Production</p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Log in through Supabase Auth to receive a signed JWT. Set{" "}
                  <code className="rounded bg-secondary px-1 py-0.5 text-[11px]">SUPABASE_JWT_SECRET</code>{" "}
                  in your backend to enable full signature verification.
                </p>
              </div>

              <Separator />

              {/* Development */}
              <div className="space-y-2.5">
                <p className="text-xs font-semibold text-foreground">Development</p>
                <p className="text-xs text-muted-foreground">
                  Generate a local signed token from the project root:
                </p>
                <div className="flex items-center justify-between rounded-lg bg-secondary border border-border px-3 py-2.5">
                  <code className="text-xs font-mono text-foreground">
                    python backend/scripts/make_token.py
                  </code>
                  <CopyButton text="python backend/scripts/make_token.py" />
                </div>
                <ol className="space-y-1.5 text-xs text-muted-foreground list-decimal list-inside leading-relaxed">
                  <li>Run the command above in your project root</li>
                  <li>Copy the token printed after <span className="font-medium text-foreground">BEARER TOKEN:</span></li>
                  <li>Paste it into the Bearer Token field above and click Save</li>
                </ol>
              </div>

              {/* Note */}
              <div className="rounded-lg bg-secondary border border-border px-3 py-2.5 text-xs text-muted-foreground">
                Dev tokens are valid for 1 year and signed with{" "}
                <code className="text-[11px]">test-secret</code>.
                Always use Supabase-signed tokens in production.
              </div>
            </CardContent>
          </Card>

        </div>{/* end grid */}
      </div>
    </div>
  );
}
