'use client';

import React, { useState, useEffect } from 'react';

export default function HappinessSystem() {
  const [language, setLanguage] = useState('English');

  useEffect(() => {
    // Dynamically apply content localization based on IP Geolocation detected in Dashboard
    const savedLanguage = localStorage.getItem('userLocationLanguage');
    if (savedLanguage) setLanguage(savedLanguage);
  }, []);

  const localizedContent: Record<string, string> = {
    "English": "Remember to take breaks, drink water, and prioritize your well-being today!",
    "Spanish": "¡Recuerda hacer pausas, beber agua y priorizar tu bienestar hoy!",
    "Hindi": "याद रखें, आज ब्रेक लें, पानी पिएं और अपनी भलाई को प्राथमिकता दें!",
    "French": "N'oubliez pas de faire des pauses, de boire de l'eau et de donner la priorité à votre bien-être aujourd'hui !"
  };

  return (
    <div style={{ padding: '2rem', background: 'linear-gradient(to right, #FDE68A, #D1FAE5)', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', textAlign: 'center' }}>
      <h2>🌻 Daily Wellness</h2>
      <p style={{ fontSize: '1.1rem', fontWeight: '500', color: '#065F46' }}>{localizedContent[language] || localizedContent["English"]}</p>
      <p style={{ fontSize: '0.85rem', color: '#6B7280', marginTop: '1rem' }}>Displaying in: {language}</p>
    </div>
  );
}