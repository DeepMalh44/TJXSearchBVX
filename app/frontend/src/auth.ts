import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

type PublicConfig = { tenantId: string; clientId: string; apiScope: string };
export let apiScope = "";

/** Build MSAL from runtime API configuration so one image works in every environment. */
export async function createMsal(): Promise<PublicClientApplication> {
  const response = await fetch("/api/config");
  if (!response.ok) throw new Error("Application configuration is unavailable");
  const config: PublicConfig = await response.json();
  apiScope = config.apiScope;
  const configuration: Configuration = {
    auth: {
      clientId: config.clientId,
      authority: `https://login.microsoftonline.com/${config.tenantId}`,
      redirectUri: window.location.origin,
    },
    cache: { cacheLocation: "sessionStorage" },
  };
  const instance = new PublicClientApplication(configuration);
  await instance.initialize();
  await instance.handleRedirectPromise();
  return instance;
}