type TelegramWebApp = {
  ready: () => void;
  expand: () => void;
  colorScheme?: "light" | "dark";
  initData?: string;
};


declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}


export function initTelegramWebApp(): TelegramWebApp | null {
  const webApp = window.Telegram?.WebApp;
  if (!webApp) {
    return null;
  }

  webApp.ready();
  webApp.expand();
  return webApp;
}
