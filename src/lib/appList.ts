// lib/appList.ts



interface AppDefinition {
  name: string;
  icon: string;
  href: string;
  capabilityKey?: string;
  permission: (user: User) => boolean;
}

export const apps: AppDefinition[] = [
  {
    name: 'Chat',
    icon: '💬',
    href: '/',
    capabilityKey: 'general_chat_app_access',
    permission: (_user) => true // Altijd zichtbaar
  },
  {
    name: 'Versimpelaar',
    icon: '🔤',
    href: '/app-launcher/versimpelaar',
    capabilityKey: 'versimpelaar_app_access',
    permission: (user) =>
      user?.role === 'admin' ||
      user?.permissions?.app_launcher?.versimpelaar
  },
  {
    name: 'Subsidies',
    icon: '💰',
    href: '/app-launcher/subsidies2',
    capabilityKey: 'chat_app_access',
    permission: (user) =>
      user?.role === 'admin' ||
      user?.permissions?.app_launcher?.subsidies
  }
];