/**
 * firebase.js
 * -----------
 * Firebase app initialization.
 * Replace the placeholder values below with the real config from:
 *   Firebase Console → Project Settings → Your apps → SDK setup and configuration
 */
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';

// TODO: Fill in real values from Firebase Console before using Firebase features.
const firebaseConfig = {
  apiKey:            'REPLACE_WITH_API_KEY',
  authDomain:        'REPLACE_WITH_PROJECT_ID.firebaseapp.com',
  projectId:         'REPLACE_WITH_PROJECT_ID',
  storageBucket:     'REPLACE_WITH_PROJECT_ID.firebasestorage.app',
  messagingSenderId: 'REPLACE_WITH_MESSAGING_SENDER_ID',
  appId:             'REPLACE_WITH_APP_ID',
};

const app = initializeApp(firebaseConfig);

// Export auth so client.js and future auth screens can use it.
export const auth = getAuth(app);

export default app;
