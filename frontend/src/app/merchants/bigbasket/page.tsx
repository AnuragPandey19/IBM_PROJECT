"use client";

import { MerchantCheckout, MerchantConfig } from "@/components/MerchantCheckout";

const BIGBASKET: MerchantConfig = {
  slug: "bigbasket",
  displayName: "BigBasket",
  tagline: "India's largest online grocery store",
  logoLetter: "B",
  primaryHex: "#84BE39",
  primaryHexDark: "#5F8B27",
  // Grocery — maps to Sparkov's grocery_pos which is a well-learned category
  category: "grocery_pos",
  products: [
    { id: "bb_veggies",    name: "Fresh Vegetables Basket",       priceInr: 320, image: "🥬" },
    { id: "bb_fruits",     name: "Seasonal Fruits Box",           priceInr: 480, image: "🍎" },
    { id: "bb_essentials", name: "Weekly Grocery Essentials",     priceInr: 1250, image: "🛒" },
    { id: "bb_monthly",    name: "Monthly Family Ration",         priceInr: 4200, image: "📦" },
    { id: "bb_hotel",      name: "Hotel Kitchen Supply Bundle",   priceInr: 65000, image: "🏨" },
    { id: "bb_restaurant", name: "Restaurant Restock (30 days)",  priceInr: 145000, image: "🍽️" },
    { id: "bb_wholesale",  name: "Wholesale Distributor Order",   priceInr: 240000, image: "🏬" },
  ],
};

export default function BigBasketCheckout() {
  return <MerchantCheckout config={BIGBASKET} />;
}
