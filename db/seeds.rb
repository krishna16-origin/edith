puts "Seeding Growkit..."

categories = {
  "Mobiles"        => "📱",
  "Electronics"    => "💻",
  "Fashion"        => "👕",
  "Home & Kitchen" => "🏠",
  "Beauty"         => "💄",
  "Books"          => "📚"
}

categories.each do |name, icon|
  Category.find_or_create_by!(name: name) { |c| c.icon = icon }
end

mobiles        = Category.find_by(name: "Mobiles")
electronics    = Category.find_by(name: "Electronics")
fashion        = Category.find_by(name: "Fashion")
home_kitchen   = Category.find_by(name: "Home & Kitchen")
beauty         = Category.find_by(name: "Beauty")
books          = Category.find_by(name: "Books")

products = [
  { name: "Nova X50 Smartphone (128GB, Midnight Blue)", category: mobiles, price: 14999, mrp: 19999,
    description: "6.5-inch display, 50MP triple camera, 5000mAh battery, octa-core processor.",
    image_url: "https://placehold.co/400x400/2874f0/ffffff?text=Nova+X50", stock: 42, rating: 4.3 },
  { name: "Pulse Air Lite (64GB, Coral Red)", category: mobiles, price: 8999, mrp: 11499,
    description: "Lightweight 5G phone with 48MP camera and all-day battery life.",
    image_url: "https://placehold.co/400x400/2874f0/ffffff?text=Pulse+Air", stock: 30, rating: 4.1 },
  { name: "Orbit Pro Max (256GB, Graphite)", category: mobiles, price: 42999, mrp: 49999,
    description: "Flagship performance chipset, 120Hz AMOLED display, 108MP camera system.",
    image_url: "https://placehold.co/400x400/2874f0/ffffff?text=Orbit+Pro", stock: 15, rating: 4.6 },

  { name: "AcoustiX Wireless Earbuds", category: electronics, price: 1999, mrp: 3499,
    description: "Active noise cancellation, 30-hour battery with charging case.",
    image_url: "https://placehold.co/400x400/fb641b/ffffff?text=Earbuds", stock: 80, rating: 4.2 },
  { name: "StreamView 43-inch Smart LED TV", category: electronics, price: 21999, mrp: 32999,
    description: "Full HD smart display with built-in streaming apps and voice remote.",
    image_url: "https://placehold.co/400x400/fb641b/ffffff?text=Smart+TV", stock: 10, rating: 4.4 },
  { name: "PowerBank 20000mAh Fast Charge", category: electronics, price: 1499, mrp: 2199,
    description: "Dual USB output, 22.5W fast charging, compact travel-friendly design.",
    image_url: "https://placehold.co/400x400/fb641b/ffffff?text=PowerBank", stock: 60, rating: 4.0 },
  { name: "GameSense Mechanical Keyboard", category: electronics, price: 2799, mrp: 3999,
    description: "RGB backlit mechanical keys with anti-ghosting for gaming.",
    image_url: "https://placehold.co/400x400/fb641b/ffffff?text=Keyboard", stock: 25, rating: 4.3 },

  { name: "Urban Fit Men's Casual Shirt", category: fashion, price: 699, mrp: 1299,
    description: "Breathable cotton-blend fabric, regular fit, machine washable.",
    image_url: "https://placehold.co/400x400/212121/ffffff?text=Shirt", stock: 100, rating: 4.0 },
  { name: "Women's Floral Wrap Dress", category: fashion, price: 999, mrp: 1799,
    description: "Flowy summer dress with adjustable waist tie, available in multiple sizes.",
    image_url: "https://placehold.co/400x400/212121/ffffff?text=Dress", stock: 55, rating: 4.2 },
  { name: "Runner Pro Sports Shoes", category: fashion, price: 1799, mrp: 2999,
    description: "Lightweight cushioned sole for running and daily training.",
    image_url: "https://placehold.co/400x400/212121/ffffff?text=Shoes", stock: 70, rating: 4.5 },

  { name: "ChefLine Non-Stick Cookware Set (5pc)", category: home_kitchen, price: 1899, mrp: 2999,
    description: "Durable non-stick coating, compatible with gas and induction tops.",
    image_url: "https://placehold.co/400x400/00897b/ffffff?text=Cookware", stock: 35, rating: 4.1 },
  { name: "AromaBrew Automatic Coffee Maker", category: home_kitchen, price: 2499, mrp: 3799,
    description: "12-cup capacity with programmable timer and keep-warm function.",
    image_url: "https://placehold.co/400x400/00897b/ffffff?text=Coffee+Maker", stock: 20, rating: 4.3 },

  { name: "GlowLux Vitamin C Face Serum", category: beauty, price: 549, mrp: 899,
    description: "Brightening serum with hyaluronic acid for daily glow.",
    image_url: "https://placehold.co/400x400/d81b60/ffffff?text=Serum", stock: 90, rating: 4.4 },

  { name: "The Art of Clean Code (Paperback)", category: books, price: 399, mrp: 599,
    description: "A practical guide to writing readable, maintainable software.",
    image_url: "https://placehold.co/400x400/6a1b9a/ffffff?text=Book", stock: 48, rating: 4.7 }
]

products.each do |attrs|
  Product.find_or_create_by!(name: attrs[:name]) do |p|
    p.category    = attrs[:category]
    p.price       = attrs[:price]
    p.mrp         = attrs[:mrp]
    p.description = attrs[:description]
    p.image_url   = attrs[:image_url]
    p.stock       = attrs[:stock]
    p.rating      = attrs[:rating]
  end
end

puts "Seeded #{Category.count} categories and #{Product.count} products."
