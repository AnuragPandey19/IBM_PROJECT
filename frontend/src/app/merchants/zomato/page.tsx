"use client";

import { MerchantCheckout, MerchantConfig } from "@/components/MerchantCheckout";

const ZOMATO: MerchantConfig = {
  slug: "zomato",
  displayName: "Zomato",
  tagline: "Order from your favorite restaurants",
  logoLetter: "Z",
  primaryHex: "#E23744",
  primaryHexDark: "#B01E29",
  // Sparkov category most similar to "food ordering online" is misc_net.
  // We use misc_net for restaurant delivery — model has learned this maps
  // to online-shopping-adjacent fraud patterns.
  category: "misc_net",
  products: [
    { id: "zomato_biryani",  name: "Chicken Biryani (Family)",     priceInr: 450, image: "🍛" },
    { id: "zomato_pizza",    name: "Margherita Pizza (Large)",     priceInr: 380, image: "🍕" },
    { id: "zomato_thali",    name: "North Indian Thali",           priceInr: 320, image: "🍽️" },
    { id: "zomato_party",    name: "Party Feast (10 people)",      priceInr: 4500, image: "🎉" },
    { id: "zomato_corp",     name: "Corporate Lunch (50 pax)",     priceInr: 45000, image: "🏢" },
    { id: "zomato_wedding",  name: "Wedding Catering (100 pax)",   priceInr: 120000, image: "💒" },
    { id: "zomato_luxury",   name: "Premium Wedding Package",      priceInr: 250000, image: "💍" },
  ],
};

export default function ZomatoCheckout() {
  return <MerchantCheckout config={ZOMATO} />;
}
