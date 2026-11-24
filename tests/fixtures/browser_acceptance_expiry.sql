-- EIMS Secure Browser Acceptance fixture only.
-- Guard prevents accidental use against operational or non-acceptance databases.
-- Only the synthetic-expiry account receives a 2-second server-side session lifetime.
-- The JWT expiry remains unchanged; this validates server-side session invalidation and reauthentication.
DO $guard$
BEGIN
  IF current_database() NOT LIKE 'eims_browser_acceptance_%' THEN
    RAISE EXCEPTION 'Refusing browser-expiry fixture outside eims_browser_acceptance_* database';
  END IF;
  IF to_regclass('public.analyzer_sessions') IS NULL THEN
    RAISE EXCEPTION 'Required public.analyzer_sessions table is missing';
  END IF;
END
$guard$;

CREATE OR REPLACE FUNCTION public.eims_browser_acceptance_expire_synthetic_session()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.username = 'synthetic-expiry' THEN
    NEW.expires_at := LEAST(NEW.expires_at, clock_timestamp() + INTERVAL '2 seconds');
  END IF;
  RETURN NEW;
END
$function$;

DROP TRIGGER IF EXISTS eims_browser_acceptance_expiry ON public.analyzer_sessions;
CREATE TRIGGER eims_browser_acceptance_expiry
BEFORE INSERT OR UPDATE OF expires_at ON public.analyzer_sessions
FOR EACH ROW
EXECUTE FUNCTION public.eims_browser_acceptance_expire_synthetic_session();
