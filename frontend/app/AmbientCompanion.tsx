'use client';

import React, { useEffect, useState, useRef } from 'react';

interface LogEntry {
  msg: string;
  timestamp: number;
  timeString: string;
}

export default function AmbientCompanion() {
  const [fallDetectionActive, setFallDetectionActive] = useState(false);
  const [wellbeingActive, setWellbeingActive] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  
  // New States for Advanced Activity & Fall Logic
  const [fallTimer, setFallTimer] = useState<number | null>(null);
  const [activity, setActivity] = useState<"STILL" | "WALKING">("STILL");
  const stillStartTime = useRef<number>(Date.now());
  const [lang, setLang] = useState('English');

  const TRANSLATIONS: Record<string, Record<string, string>> = {
    "English": {
      "sosSent": "SOS Alert being sent.",
      "alertCancelled": "Alert cancelled.",
      "fallAlert": "It looks like you've fallen. Cancel in 10 seconds or SOS will be sent.",
      "sitAlert": "You have been sitting for a long time. Please drink some water and take a walk.",
      "nightAlert": "It's late. Screen turned to grayscale for your eye health. Please sleep.",
      "billAlert": "Your internet bill is pending. Shall I pay it via your default payment method?",
      "billSuccess": "Payment successful. I have paid the bill.",
      "billCancel": "Okay, payment cancelled."
    },
    "Hindi": {
      "sosSent": "एसओएस (SOS) अलर्ट भेजा जा रहा है।",
      "alertCancelled": "अलर्ट कैंसिल कर दिया गया है।",
      "fallAlert": "लगता है आप गिर गए हैं? 10 सेकंड में कैंसल करें वरना SOS चला जाएगा।",
      "sitAlert": "पापा, आप काफी देर से बैठे हैं, कृपया थोड़ा पानी पी लीजिए और टहल लीजिए।",
      "nightAlert": "रात बहुत हो चुकी है। आपकी आँखों की सेहत के लिए स्क्रीन को ग्रे कर दिया गया है। कृपया फोन रख दें और सो जाएं।",
      "billAlert": "आपका इंटरनेट बिल पेंडिंग है। क्या मैं आपके डिफ़ॉल्ट यूपीआई से पे कर दूँ?",
      "billSuccess": "पेमेंट सक्सेसफुल। मैंने बिल भर दिया है।",
      "billCancel": "ठीक है, मैंने पेमेंट कैंसिल कर दी है।"
    },
    "Urdu": {
      "sosSent": "ایس او ایس الرٹ بھیجا جا رہا ہے۔",
      "alertCancelled": "الرٹ کینسل کر دیا گیا ہے۔",
      "fallAlert": "لگتا ہے آپ گر گئے ہیں؟ دس سیکنڈ میں کینسل کریں ورنہ ایس او ایس چلا جائے گا۔",
      "sitAlert": "پاپا، آپ کافی دیر سے بیٹھے ہیں، براہ کرم تھوڑا پانی پی لیجیے اور چہل قدمی کر لیں۔",
      "nightAlert": "رات بہت ہو چکی ہے۔ آپ کی آنکھوں کی صحت کے لیے سکرین کو گرے کر دیا گیا ہے۔ براہ کرم فون رکھ دیں اور سو جائیں۔",
      "billAlert": "آپ کا انٹرنیٹ بل پینڈنگ ہے۔ کیا میں آپ کے ڈیفالٹ یو پی آئی سے پے کر دوں؟",
      "billSuccess": "پیمنٹ کامیاب۔ میں نے بل بھر دیا ہے۔",
      "billCancel": "ٹھیک ہے، میں نے پیمنٹ کینسل کر دی ہے۔"
    },
    "Spanish": {
      "sosSent": "Alerta SOS enviada.",
      "alertCancelled": "Alerta cancelada.",
      "fallAlert": "Parece que te has caído. Cancela en 10 segundos o se enviará el SOS.",
      "sitAlert": "Llevas mucho tiempo sentado. Por favor bebe agua y da un paseo.",
      "nightAlert": "Es tarde. La pantalla está en escala de grises para tu salud ocular. Por favor duerme.",
      "billAlert": "Tu factura de internet está pendiente. ¿La pago a través de tu método predeterminado?",
      "billSuccess": "Pago exitoso. Factura pagada.",
      "billCancel": "De acuerdo, pago cancelado."
    },
    "French": {
      "sosSent": "Alerte SOS en cours d'envoi.",
      "alertCancelled": "Alerte annulée.",
      "fallAlert": "Il semble que vous soyez tombé. Annulez dans 10 secondes ou le SOS sera envoyé.",
      "sitAlert": "Vous êtes assis depuis longtemps. Veuillez boire de l'eau et vous promener.",
      "nightAlert": "Il est tard. L'écran est en niveaux de gris pour vos yeux. S'il vous plaît, dormez.",
      "billAlert": "Votre facture Internet est en attente. Dois-je la payer via votre méthode par défaut?",
      "billSuccess": "Paiement réussi. Facture payée.",
      "billCancel": "D'accord, paiement annulé."
    }
  };

  // Load and auto-delete logs older than 24 hours
  useEffect(() => {
    const savedLang = localStorage.getItem('userLocationLanguage');
    if (savedLang) setLang(savedLang);

    const saved = localStorage.getItem('ambient_logs');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        const now = Date.now();
        const validLogs = parsed.filter((log: LogEntry) => now - log.timestamp < 24 * 60 * 60 * 1000);
        setLogs(validLogs);
        if (validLogs.length !== parsed.length) {
          localStorage.setItem('ambient_logs', JSON.stringify(validLogs));
        }
      } catch (e) {}
    }

    // Periodically clean up logs every hour while app is open
    const cleanupInterval = setInterval(() => {
      setLogs(prev => {
        const now = Date.now();
        const validLogs = prev.filter(log => now - log.timestamp < 24 * 60 * 60 * 1000);
        if (validLogs.length !== prev.length) {
          localStorage.setItem('ambient_logs', JSON.stringify(validLogs));
        }
        return validLogs;
      });
    }, 60 * 60 * 1000);

    return () => clearInterval(cleanupInterval);
  }, []);

  const addLog = (msg: string) => {
    const newLog = {
      msg,
      timestamp: Date.now(),
      timeString: new Date().toLocaleTimeString()
    };
    setLogs(prev => {
      const updated = [newLog, ...prev].slice(0, 100); // Keep up to 100 most recent logs within the 24h window
      localStorage.setItem('ambient_logs', JSON.stringify(updated));
      return updated;
    });
  };

  const speak = (textKey: string) => {
    const text = TRANSLATIONS[lang]?.[textKey] || TRANSLATIONS["English"][textKey] || textKey;
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const langMap: Record<string, string> = {
          "English": "en-US", "Hindi": "hi-IN", "Spanish": "es-ES", "French": "fr-FR",
          "Urdu": "ur-PK"
      };
      utterance.lang = langMap[lang] || 'en-US';
      window.speechSynthesis.speak(utterance);
    }
  };

  // 1. Fall Detection Timer Logic (Step 1.2 & 1.3)
  useEffect(() => {
    if (fallTimer === null) return;
    
    if (fallTimer > 0) {
      const timer = setTimeout(() => setFallTimer(fallTimer - 1), 1000);
      return () => clearTimeout(timer);
    } else if (fallTimer === 0) {
      // Timer finished! Send SOS
      addLog("🚨 SMS Sent to emergency contact: Fall Detected!");
      speak("sosSent");
      
      // Native SMS Intent trigger
      if (typeof window !== 'undefined') {
        window.open('sms:?body=Emergency! I might have fallen and need help. Please check on me.');
      }
      
      setFallTimer(null); // Reset after sending
    }
  }, [fallTimer]);

  const cancelSOS = () => {
    setFallTimer(null);
    addLog("✅ User cancelled SOS.");
    speak("alertCancelled");
  };

  // 2. Activity Recognition & Fall Sensor (Step 1.1)
  useEffect(() => {
    if (!fallDetectionActive) return;

    const handleMotion = (event: DeviceMotionEvent) => {
      const acc = event.accelerationIncludingGravity;
      if (!acc || acc.x === null || acc.y === null || acc.z === null) return;
      
      // Calculate magnitude of acceleration vector
      const magnitude = Math.sqrt(acc.x * acc.x + acc.y * acc.y + acc.z * acc.z);
      
      // Activity Recognition (Battery Optimized: Avoid setting state if unchanged)
      // 9.8 is gravity. Magnitudes around 11-15 indicate walking/movement.
      if (magnitude > 11 && magnitude < 19) {
        if (activity === "STILL") {
          setActivity("WALKING");
          stillStartTime.current = Date.now(); // Reset still timer
        }
      } else if (magnitude <= 11) {
        if (activity === "WALKING") {
          // Only switch back to STILL if it settles (debounce logic could be added here)
          setActivity("STILL");
          stillStartTime.current = Date.now();
        }
      }

      // Fall Detection: Standard gravity is ~9.8 m/s^2. A sudden fall creates a spike > 20 m/s^2 (approx 2g)
      if (magnitude > 20 && fallTimer === null) {
        setFallTimer(10); // Start 10-second countdown
        addLog("⚠️ Sudden spike > 2g detected. Possible fall!");
        speak("fallAlert"); 
      }
    };

    window.addEventListener('devicemotion', handleMotion);
    addLog("Fall Detection sensors activated.");
    return () => {
      window.removeEventListener('devicemotion', handleMotion);
    };
  }, [fallDetectionActive, fallTimer, activity]);

  // 3. Background AI Context & Reasoning Logger (Step 2 & 4 - 5 Minute Interval)
  useEffect(() => {
    // Logging every 5 minutes (using 300000 ms, shortened to 10s for testing ease if you want, but strictly set to 5 mins)
    const interval = setInterval(() => {
      const minutesStill = Math.floor((Date.now() - stillStartTime.current) / 60000);
      
      addLog(`[Sensor Data] User is currently ${activity}. Been STILL for ${minutesStill} minutes.`);
      
      // Step 2.2 & 2.3: Local LLM Reasoning Simulation
      if (activity === "STILL" && minutesStill >= 60) {
        addLog("🤖 AI Brain: 'User has been sitting for over 1 hour. Suggesting hydration.'");
        speak("sitAlert");
      } else if (activity === "WALKING") {
        addLog("🤖 AI Brain: 'User is active. No intervention needed.'");
      }

    }, 5 * 60 * 1000); // 5 Minutes

    return () => clearInterval(interval);
  }, [activity]);


  // 4. Digital Wellbeing (Late Night Grayscale & Posture Coach)
  useEffect(() => {
    if (!wellbeingActive) {
      document.documentElement.style.filter = 'none';
      return;
    }

    addLog("Digital Wellbeing monitor activated.");

    const checkTime = () => {
      const hour = new Date().getHours();
      // If time is between 11 PM (23) and 5 AM
      if (hour >= 23 || hour < 5) {
        document.documentElement.style.filter = 'grayscale(100%)';
        document.documentElement.style.transition = 'filter 2s ease';
        addLog("Late night detected. Screen turned to grayscale.");
        speak("nightAlert");
      } else {
        document.documentElement.style.filter = 'none';
      }
    };

    // Check immediately and then every minute
    checkTime();
    const interval = setInterval(checkTime, 60000);
    return () => {
      clearInterval(interval);
      document.documentElement.style.filter = 'none';
    };
  }, [wellbeingActive]);

  // 3. Automated Digital Tasks (Voice Execution)
  const executeAutomatedTask = () => {
    addLog("Analyzing calendar and pending bills...");
    setTimeout(() => {
      speak("billAlert");
      const userResponse = window.confirm(TRANSLATIONS[lang]?.billAlert || TRANSLATIONS["English"].billAlert);
      if (userResponse) {
        addLog("Executing background payment via Intents...");
        speak("billSuccess");
        addLog("✅ Payment Successful.");
      } else {
        speak("billCancel");
        addLog("❌ Payment Cancelled by user.");
      }
    }, 1000);
  };

  // Request permissions for sensors (iOS requires explicit permission for DeviceMotion)
  const requestSensorPermission = async () => {
    if (typeof (DeviceMotionEvent as any).requestPermission === 'function') {
      try {
        const permissionState = await (DeviceMotionEvent as any).requestPermission();
        if (permissionState === 'granted') {
          setFallDetectionActive(true);
        } else {
          alert("Sensor permission denied.");
        }
      } catch (console) {
        alert("Failed to get sensor permissions.");
      }
    } else {
      // Non-iOS devices usually don't require explicit permission
      setFallDetectionActive(!fallDetectionActive);
    }
  };

  return (
    <div style={{ background: 'white', padding: '2rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
      <div style={{ marginBottom: '2rem', borderBottom: '2px solid #E5E7EB', paddingBottom: '1rem' }}>
        <h2 style={{ margin: '0 0 0.5rem 0', color: '#111827', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          📱 Smartphone-as-a-Robot (On-Device Companion)
        </h2>
        <p style={{ color: '#6B7280', margin: 0 }}>
          यह एआई यूजर की एक्टिविटी को 24/7 मॉनिटर करके हेल्थ, प्राइवेसी और डिजिटल ऑटोमेशन को मैनेज करता है।
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        
        {/* Elderly Care / Health Card */}
        <div style={{ padding: '1.5rem', background: fallTimer !== null ? '#FEF2F2' : '#F9FAFB', border: `2px solid ${fallTimer !== null ? '#EF4444' : '#E5E7EB'}`, borderRadius: '8px' }}>
          <h3 style={{ marginTop: 0, color: '#1F2937', display: 'flex', justifyContent: 'space-between' }}>
            🏥 Elderly Care
            <span style={{ fontSize: '0.8rem', background: activity === 'WALKING' ? '#10B981' : '#6B7280', color: 'white', padding: '0.2rem 0.5rem', borderRadius: '12px' }}>
              {activity}
            </span>
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#4B5563' }}>
            ایکسیلیرومیٹر (Accelerometer) کے ذریعے گرنے کا پتہ لگاتا ہے۔ (ٹیسٹ کے لیے فون کو زور سے ہلائیں)
          </p>
          <button 
            onClick={requestSensorPermission}
            style={{ padding: '0.75rem 1rem', width: '100%', background: fallDetectionActive ? '#EF4444' : '#3B82F6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
            {fallDetectionActive ? '🛑 Stop Fall Detection' : '▶️ Enable Fall Detection (Sensors)'}
          </button>
          
          {/* Fall Detected Warning UI */}
          {fallTimer !== null && (
            <div style={{ marginTop: '1rem', padding: '1rem', background: '#EF4444', color: 'white', borderRadius: '8px', textAlign: 'center', animation: 'pulse 1s infinite' }}>
              <h4 style={{ margin: '0 0 0.5rem 0' }}>🚨 Fall Detected!</h4>
              <p style={{ margin: '0 0 1rem 0' }}>Sending SOS SMS in {fallTimer} seconds...</p>
              <button onClick={cancelSOS} style={{ padding: '0.5rem 2rem', background: 'white', color: '#EF4444', fontWeight: 'bold', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Cancel SOS</button>
            </div>
          )}
        </div>

        {/* Digital Wellbeing Card */}
        <div style={{ padding: '1.5rem', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: '8px' }}>
          <h3 style={{ marginTop: 0, color: '#1F2937' }}>🌙 Digital Wellbeing Coach</h3>
          <p style={{ fontSize: '0.9rem', color: '#4B5563' }}>
            रात 11 बजे के बाद फोन चलाने पर स्क्रीन को ग्रे-स्केल (Grayscale) कर देता है और सोने की सलाह देता है।
          </p>
          <button 
            onClick={() => setWellbeingActive(!wellbeingActive)}
            style={{ padding: '0.75rem 1rem', width: '100%', background: wellbeingActive ? '#10B981' : '#374151', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
            {wellbeingActive ? '✅ Wellbeing Coach Active' : '▶️ Enable Wellbeing Coach'}
          </button>
        </div>

        {/* Action Layer Card */}
        <div style={{ padding: '1.5rem', background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: '8px' }}>
          <h3 style={{ marginTop: 0, color: '#1F2937' }}>⚡ Action Layer (Auto Tasks)</h3>
          <p style={{ fontSize: '0.9rem', color: '#4B5563' }}>
            कैलेंडर और पेंडिंग बिल्स का एनालिसिस करके खुद वॉयस कमांड से पेमेंट कन्फर्मेशन मांगता है।
          </p>
          <button 
            onClick={executeAutomatedTask}
            style={{ padding: '0.75rem 1rem', width: '100%', background: '#8B5CF6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
            🎙️ Simulate Bill Payment Task
          </button>
        </div>

      </div>

      {/* Logs Window */}
      <div style={{ background: '#111827', borderRadius: '8px', padding: '1rem', color: '#10B981', fontFamily: 'monospace', height: '200px', overflowY: 'auto' }}>
        <h4 style={{ margin: '0 0 0.5rem 0', color: '#9CA3AF', borderBottom: '1px solid #374151', paddingBottom: '0.5rem' }}>&gt;_ Agent System Logs</h4>
        {logs.length === 0 ? (
          <span style={{ color: '#4B5563' }}>Waiting for perception layer inputs...</span>
        ) : (
          logs.map((log, i) => (
            <div key={i} style={{ marginBottom: '0.25rem' }}>[{log.timeString}] {log.msg}</div>
          ))
        )}
      </div>
    </div>
  );
}