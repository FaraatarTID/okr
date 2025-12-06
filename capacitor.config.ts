import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
    appId: 'com.okrtracker.app',
    appName: 'OKR Tracker',
    webDir: 'dist',
    server: {
        androidScheme: 'https'
    },
    plugins: {
        SplashScreen: {
            launchShowDuration: 2000,
            backgroundColor: '#1e293b',
            showSpinner: false
        },
        StatusBar: {
            style: 'dark',
            backgroundColor: '#1e293b'
        }
    }
};

export default config;
