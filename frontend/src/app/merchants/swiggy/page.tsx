"use client";

import { MerchantCheckout, MerchantConfig } from "@/components/MerchantCheckout";

const SWIGGY: MerchantConfig = {
  slug: "swiggy",
  displayName: "Swiggy",
  tagline: "Food, Instamart & more · Delivered in 30 min",
  logoLetter: "S",
  primaryHex: "#FC8019",
  primaryHexDark: "#D66A0F",
  category: "misc_net",
  products: [
    { id: "swiggy_meal",       name: "South Indian Combo",           priceInr: 280, image: "🥘" },
    { id: "swiggy_pizza",      name: "Peri Peri Chicken Pizza",      priceInr: 420, image: "🍕" },
    { id: "swiggy_biryani",    name: "Hyderabadi Dum Biryani",       priceInr: 380, image: "🍚" },
    { id: "swiggy_family",     name: "Family Feast (6 people)",      priceInr: 2200, image: "🍽️" },
    { id: "swiggy_office",     name: "Office Lunch (100 pax)",       priceInr: 55000, image: "🏢" },
    { id: "swiggy_event",      name: "Corporate Event (300 pax)",    priceInr: 180000, image: "🎪" },
    { id: "swiggy_conference", name: "Conference Catering",          priceInr: 280000, image: "🏛️" },
  ],
};

export default function SwiggyCheckout() {
  return <MerchantCheckout config={SWIGGY} />;
}
