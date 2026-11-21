"use client";

import { createContext, useContext, useMemo, useState } from "react";

export type Language = "en" | "hi";

const hindi: Record<string, string> = {
  "Language": "भाषा",
  "English": "अंग्रेज़ी",
  "Hindi": "हिन्दी",
  "Overview": "अवलोकन",
  "Documents": "दस्तावेज़",
  "Timeline": "समयरेखा",
  "Emergency": "आपातकाल",
  "Family": "परिवार",
  "Data & privacy": "डेटा और गोपनीयता",
  "My profile": "मेरी प्रोफ़ाइल",
  "Log out": "लॉग आउट",
  "Create your account": "अपना खाता बनाएं",
  "Welcome back": "वापसी पर स्वागत है",
  "Begin with a private, patient-reported health profile.": "एक निजी, रोगी द्वारा दी गई स्वास्थ्य प्रोफ़ाइल से शुरू करें।",
  "Log in to continue to your health profile.": "अपनी स्वास्थ्य प्रोफ़ाइल जारी रखने के लिए लॉग इन करें।",
  "Full name": "पूरा नाम",
  "Email address": "ईमेल पता",
  "Password": "पासवर्ड",
  "Use at least 12 characters.": "कम से कम 12 अक्षर इस्तेमाल करें।",
  "I agree to the": "मैं सहमत हूँ:",
  "and acknowledge the": "और मैंने पढ़ा है:",
  "Create account": "खाता बनाएं",
  "Log in": "लॉग इन",
  "Already registered? ": "पहले से खाता है? ",
  "New to Medical Passport? ": "Medical Passport पर नए हैं? ",
  "Privacy notice": "गोपनीयता सूचना",
  "Terms of use": "उपयोग की शर्तें",
  "My consents": "मेरी सहमतियाँ",
  "Export my data": "मेरा डेटा निर्यात करें",
  "Delete my account": "मेरा खाता हटाएं",
  "Text extraction and review": "पाठ निष्कर्षण और समीक्षा",
  "Patient name": "रोगी का नाम",
  "Diagnosis": "निदान",
  "Medication": "दवा",
  "Age": "उम्र",
  "Terms": "शर्तें",
  "Privacy Notice": "गोपनीयता सूचना",
  "Allergy": "एलर्जी",
  "Lab result": "जांच परिणाम",
  "Procedure": "प्रक्रिया",
  "Blood group": "रक्त समूह",
  "Known allergies": "ज्ञात एलर्जी",
  "Critical conditions": "गंभीर स्थितियाँ",
  "Current medications": "वर्तमान दवाएँ",
  "Emergency contacts": "आपातकालीन संपर्क",
  "Consent-controlled access": "सहमति से नियंत्रित पहुँच",
  "Emergency profile": "आपातकालीन प्रोफ़ाइल",
  "Choose information to share": "साझा करने की जानकारी चुनें",
  "Link expires": "लिंक की अवधि",
  "Label (optional)": "नाम (वैकल्पिक)",
  "Create emergency QR": "आपातकालीन QR बनाएं",
  "Print wallet card": "वॉलेट कार्ड प्रिंट करें",
  "Download QR": "QR डाउनलोड करें",
  "Active and previous links": "सक्रिय और पुराने लिंक",
  "Your data, your control": "आपका डेटा, आपका नियंत्रण",
  "Source-linked history": "स्रोत से जुड़ा इतिहास",
  "Medical timeline": "चिकित्सा समयरेखा",
  "FHIR R4-aligned export": "FHIR R4-अनुरूप निर्यात",
  "Download FHIR export": "FHIR निर्यात डाउनलोड करें",
  "Privacy": "गोपनीयता",
  "Return to signup": "साइन अप पर लौटें",
};

type LanguageContextValue = { language: Language; setLanguage: (language: Language) => void; t: (text: string) => string };
const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ initialLanguage, children }: { initialLanguage: Language; children: React.ReactNode }) {
  const [language, setCurrentLanguage] = useState<Language>(initialLanguage);
  const setLanguage = (next: Language) => {
    document.cookie = `mp_language=${next}; Path=/; Max-Age=31536000; SameSite=Lax`;
    document.documentElement.lang = next;
    setCurrentLanguage(next);
  };
  const value = useMemo(() => ({ language, setLanguage, t: (text: string) => language === "hi" ? (hindi[text] ?? text) : text }), [language]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("LanguageProvider is missing");
  return value;
}
