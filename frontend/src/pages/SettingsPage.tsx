import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Save, Eye, EyeOff, LogOut, CheckCircle2, XCircle,
  Loader2, Clock, Terminal, Copy, Check,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
    const daysLeft = Math.floor(msLeft / (1000 * 60 * 60 * 24));
    return { daysLeft, expired: msLeft <= 0 };
  } catch {
    return null;
  }
}

// ── Schema ────────────────────────────────────────────────────────────────────

const settingsSchema = z.object({
  apiBaseUrl:  z.string().url("Must be a valid URL"),
  bearerToken: z.string().min(1, "Bearer token is required"),
});

type SettingsForm = z.infer<typeof settingsSchema>;

// ── Copy button ───────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      type="button"
      onClick={copy}
      className="text-muted-foreground hover:text-foreground transition-colors"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function SettingsPage() {
  const {
    apiBaseUrl, bearerToken, claims, isAuthenticated,
    setApiBaseUrl, setBearerToken, clearSession,
  } = useSessionStore();

  const [showToken, setShowToken]         = useState(false);
  const [testStatus, setTestStatus]       = useState<"idle" | "loading" | "ok" | "fail">("idle");

  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<SettingsForm>({
    resolver: zodResolver(settingsSchema),
    defaultValues: { apiBaseUrl, bearerToken },
  });

  const onSubmit = (data: SettingsForm) => {
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

      <div className="flex-1 overflow-auto p-6 max-w-2xl space-y-5">

        {/* ── Auth status ──────────────────────────────────────────────── */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Auth Status</CardTitle>
              <Badge variant={isAuthenticated ? "success" : "danger"}>
                {isAuthenticated ? "Authenticated" : "Not authenticated"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {claims ? (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-muted-foreground mb-0.5">Merchant ID</p>
                  <p className="font-mono text-xs truncate">{claims.merchant_id}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-0.5">Email</p>
                  <p className="text-xs truncate">{claims.email}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-0.5">Role</p>
                  <p className="text-xs capitalize">{claims.role}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-0.5">Token Expiry</p>
                  {expiry ? (
                    <p className={`text-xs font-medium flex items-center gap-1 ${
                      expiry.expired ? "text-red-400" : expiry.daysLeft < 7 ? "text-amber-400" : "text-emerald-400"
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
              <p className="text-xs text-muted-foreground">
                Paste a bearer token below to authenticate.
              </p>
            )}
          </CardContent>
        </Card>

        {/* ── Connection form ───────────────────────────────────────────── */}
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Connection</CardTitle>
              <CardDescription>Backend URL and bearer token</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="apiBaseUrl" className="text-xs font-medium text-muted-foreground">
                  API Base URL
                </label>
                <div className="flex gap-2">
                  <Input
                    id="apiBaseUrl"
                    type="url"
                    placeholder="http://localhost:8000"
                    className="flex-1"
                    {...register("apiBaseUrl")}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="shrink-0 gap-1.5 text-xs h-9 px-3"
                    onClick={testConnection}
                    disabled={testStatus === "loading"}
                  >
                    {testStatus === "loading" ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : testStatus === "ok" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    ) : testStatus === "fail" ? (
                      <XCircle className="h-3.5 w-3.5 text-red-400" />
                    ) : null}
                    {testStatus === "idle" ? "Test" : testStatus === "loading" ? "Testing…" : testStatus === "ok" ? "Online" : "Offline"}
                  </Button>
                </div>
                {errors.apiBaseUrl && (
                  <p className="text-xs text-destructive">{errors.apiBaseUrl.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label htmlFor="bearerToken" className="text-xs font-medium text-muted-foreground">
                  Bearer Token
                </label>
                <div className="relative">
                  <Input
                    id="bearerToken"
                    type={showToken ? "text" : "password"}
                    placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    className="pr-9 font-mono text-xs"
                    {...register("bearerToken")}
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken((v) => !v)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    aria-label={showToken ? "Hide token" : "Show token"}
                  >
                    {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </button>
                </div>
                {errors.bearerToken && (
                  <p className="text-xs text-destructive">{errors.bearerToken.message}</p>
                )}
              </div>

              <div className="flex items-center justify-between pt-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => { clearSession(); toast.success("Session cleared"); }}
                  className="gap-1.5 text-xs text-muted-foreground hover:text-destructive"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Clear session
                </Button>
                <Button type="submit" size="sm" disabled={!isDirty} className="gap-1.5 text-xs">
                  <Save className="h-3.5 w-3.5" />
                  Save
                </Button>
              </div>
            </CardContent>
          </Card>
        </form>

        {/* ── Generate token guide ──────────────────────────────────────── */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-sm">Generate a Test Token</CardTitle>
            </div>
            <CardDescription>
              Run this command in your project root to create a signed bearer token
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-md bg-secondary/50 border border-border p-3 font-mono text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">$ </span>
                <div className="flex items-center gap-2">
                  <span className="text-foreground">python make_token.py</span>
                  <CopyButton text="python make_token.py" />
                </div>
              </div>
            </div>

            <ol className="space-y-2 text-xs text-muted-foreground list-decimal list-inside">
              <li>Open a terminal in <span className="font-mono bg-secondary px-1 py-0.5 rounded text-[10px]">D:\d2c-ai-employee</span></li>
              <li>Make sure your virtual env is active (<span className="font-mono bg-secondary px-1 py-0.5 rounded text-[10px]">.venv\Scripts\activate</span>)</li>
              <li>Run the command above</li>
              <li>Copy the token printed under <span className="text-foreground font-medium">YOUR BEARER TOKEN:</span></li>
              <li>Paste it into the Bearer Token field above and click Save</li>
            </ol>

            <div className="rounded-md border border-primary/20 bg-primary/5 px-3 py-2.5 text-xs text-primary/80">
              The generated token is valid for 1 year and uses your merchant ID from <span className="font-mono">make_token.py</span>.
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
