import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { ArrowRight, CalendarDays, Eye, EyeOff, Layers, LoaderCircle, Mail, ShieldCheck, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { GoogleLogin } from "@react-oauth/google";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { loginThunk, googleLoginThunk } from "@/store/authSlice";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { status, error: serverError } = useAppSelector((state) => state.auth);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const googleEnabled = !!import.meta.env.VITE_GOOGLE_CLIENT_ID;

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (values: LoginFormValues) => {
    const result = await dispatch(loginThunk(values));
    if (loginThunk.fulfilled.match(result)) {
      navigate(`/${result.payload.role}/dashboard`);
    }
  };

  const busy = isSubmitting || status === "loading";

  return (
    <main className="flex min-h-svh bg-[#fafbf8] p-3 text-slate-900 sm:p-5">
      {/* Left hero panel */}
      <section aria-label="Your people workspace" className="relative hidden w-[48%] shrink-0 overflow-hidden rounded-[28px] bg-[#173e32] lg:flex">
        <div aria-hidden="true" className="pointer-events-none absolute -right-48 -top-48 h-[580px] w-[580px] rounded-full border border-white/10" />
        <div aria-hidden="true" className="pointer-events-none absolute -right-32 -top-32 h-[450px] w-[450px] rounded-full border border-white/10" />
        <div className="relative flex w-full flex-col px-10 py-10 xl:px-14">
          <div className="flex items-center gap-3 text-lg font-semibold tracking-tight text-white">
            <span className="flex size-10 items-center justify-center rounded-xl bg-white/10"><Layers className="size-5" aria-hidden="true" /></span>
            Agentic<span className="-ml-2 font-normal text-white/65">HRMS</span>
          </div>
          <div className="my-auto py-14">
          <p className="mb-6 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-[#c6e6a3]">
            <span className="size-1.5 rounded-full bg-[#c6e6a3]" /> A little less admin. A lot more people.
          </p>
          <h2 className="max-w-lg text-5xl font-medium leading-[1.12] tracking-[-0.045em] text-white xl:text-6xl">
            Good work starts<br />with <span className="font-serif italic text-[#c6e6a3]">your people.</span>
          </h2>
          <p className="mt-6 max-w-sm text-base leading-7 text-white/70">
            One workspace for your team, time off, and everyday HR. More clarity for everyone.
          </p>
          <div className="mt-10 rounded-2xl border border-white/15 bg-white/[0.06] p-5 xl:p-6">
            <p className="mb-5 text-xs font-medium uppercase tracking-widest text-white/60">Everything in its place</p>
            <div className="space-y-5">
              {[{ icon: Users, title: "Stay connected", description: "Your people and profiles, together." }, { icon: CalendarDays, title: "Make room for life", description: "Attendance and time off, made simple." }, { icon: ShieldCheck, title: "A workspace for every role", description: "The right access for every teammate." }].map(({ icon: Icon, title, description }) => (
                <div key={title} className="flex items-center gap-4">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-[#c6e6a3]"><Icon className="size-5" aria-hidden="true" /></span>
                  <div><p className="text-sm font-medium text-white">{title}</p><p className="mt-1 text-xs leading-5 text-white/65">{description}</p></div>
                </div>
              ))}
            </div>
          </div>
          </div>
          <p className="text-xs text-white/55">Built around people. Designed for every workday.</p>
        </div>
      </section>

      {/* Right form panel */}
      <section aria-labelledby="login-title" className="flex min-w-0 flex-1 flex-col px-4 py-6 sm:px-10 lg:px-12">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#173e32] lg:justify-end">
          <Layers className="size-5" aria-hidden="true" /><span>Agentic HRMS</span>
        </div>
        <div className="mx-auto my-auto w-full max-w-sm py-14 sm:py-16">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#51735d]">
            Your everyday workspace
          </p>
          <h1 id="login-title" className="mt-4 text-4xl font-semibold leading-tight tracking-tight sm:text-[42px]">
            Welcome back.
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            Sign in with your company account to get started.
          </p>

          <form noValidate onSubmit={handleSubmit(onSubmit)} aria-busy={busy} className="mt-9 space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email">Work email</Label>
              <div className="relative">
              <Mail className="pointer-events-none absolute left-3.5 top-4 size-4 text-slate-400" aria-hidden="true" />
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                className="h-12 rounded-xl border-slate-300 bg-white pl-10 shadow-none focus-visible:ring-2 focus-visible:ring-[#51735d]"
                disabled={busy}
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? "email-error" : undefined}
                autoComplete="email"
                {...register("email")}
              />
              </div>
              {errors.email && <p id="email-error" role="alert" className="text-sm text-red-700">{errors.email.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                className="h-12 rounded-xl border-slate-300 bg-white pr-12 shadow-none focus-visible:ring-2 focus-visible:ring-[#51735d]"
                disabled={busy}
                aria-invalid={!!errors.password}
                aria-describedby={errors.password ? "password-error" : undefined}
                autoComplete="current-password"
                {...register("password")}
              />
              <button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} className="absolute right-1 top-1 flex size-10 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-[#51735d]">
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
              </div>
              {errors.password && <p id="password-error" role="alert" className="text-sm text-red-700">{errors.password.message}</p>}
            </div>
            {serverError && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{serverError}</p>}
            <Button type="submit" className="h-12 w-full rounded-xl bg-[#173e32] text-white hover:bg-[#245442] focus-visible:ring-2 focus-visible:ring-[#51735d] focus-visible:ring-offset-2" disabled={busy}>
              {busy ? <><LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" /> Signing in...</> : <>Sign in to your workspace <ArrowRight className="size-4" aria-hidden="true" /></>}
            </Button>
            {googleEnabled && (
              <>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="flex-1 border-t" />
                  or
                  <span className="flex-1 border-t" />
                </div>
                <div className="flex justify-center">
                  <GoogleLogin
                    text="signin_with"
                    onSuccess={async (cred) => {
                      if (!cred.credential) return;
                      const email = JSON.parse(atob(cred.credential.split(".")[1])).email as string;
                      const result = await dispatch(googleLoginThunk({ idToken: cred.credential, email }));
                      if (googleLoginThunk.fulfilled.match(result)) {
                        navigate(`/${result.payload.role}/dashboard`);
                      }
                    }}
                    onError={() => setGoogleError("Google sign-in was cancelled.")}
                  />
                </div>
              </>
            )}
            {googleError && <p role="alert" className="text-center text-sm text-red-700">{googleError}</p>}
            <p className="pt-2 text-center text-xs leading-6 text-slate-500">
              Need an account or help signing in?<br /><span className="font-medium text-slate-700">Contact your HR team.</span>
            </p>
          </form>
        </div>
        <p className="text-center text-xs text-slate-500">© {new Date().getFullYear()} Agentic HRMS</p>
      </section>
    </main>
  );
}
