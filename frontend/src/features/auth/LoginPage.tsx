import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router";
import { Sparkles, Bot, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { loginThunk } from "@/store/authSlice";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { status, error: serverError } = useAppSelector((state) => state.auth);

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
    <div className="flex min-h-screen bg-background">
      {/* Left hero panel */}
      <div className="hidden w-[45%] shrink-0 md:block bg-black relative overflow-hidden">
        <div className="flex h-full flex-col justify-center px-12">
          <div className="mb-8 inline-flex w-fit items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm text-white/80">
            <Sparkles className="h-4 w-4" />
            AI-Powered HRMS
          </div>

          <h1 className="text-5xl font-bold leading-tight text-white">
            Let AI Run Your
            <br />
            HR Workflows
          </h1>

          <p className="mt-4 max-w-md text-lg text-white/60">
            Manage employees, attendance, and leaves with an intelligent
            assistant that understands your policies.
          </p>

          <div className="mt-10 space-y-5">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10">
                <Bot className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-white">Agentic AI Assistant</p>
                <p className="text-sm text-white/60">
                  Ask questions, get answers, take action — instantly
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10">
                <ShieldCheck className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="font-semibold text-white">Role-Based Access</p>
                <p className="text-sm text-white/60">
                  Granular permissions for Admin, HR, and Employees
                </p>
              </div>
            </div>
          </div>

          <div className="absolute bottom-10 left-12 right-12 border-t border-white/10 pt-6 text-sm text-white/40">
            © 2026 Agentic HRMS. All rights reserved.
          </div>
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex flex-1 items-center justify-center px-6 py-10">
        <div className="w-full max-w-sm">
          <p className="text-lg font-semibold tracking-tight">
            Agentic<span className="text-accent">HRMS</span>
          </p>

          <h1 className="font-display mt-6 text-[32px] font-semibold leading-tight">
            Hi, there!
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Welcome back — sign in with your company account
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4">
            <div className="space-y-1">
              <Label htmlFor="email">Email Id</Label>
              <Input
                id="email"
                type="email"
                placeholder="xyz@gmail.com"
                autoComplete="email"
                {...register("email")}
              />
              {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                autoComplete="current-password"
                {...register("password")}
              />
              {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
            </div>
            {serverError && <p className="text-sm text-destructive">{serverError}</p>}
            <Button type="submit" className="w-full rounded-full" disabled={busy}>
              {busy ? "Signing in..." : "Sign in"}
            </Button>
            <p className="text-center text-xs text-muted-foreground">
              Accounts are created by HR — contact them if you can't sign in.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}