# Growkit 🛒

A Flipkart-style online shopping app built with **Ruby on Rails**, SQLite and plain CSS (no JS framework required). Users log in with just their **name and mobile number** — no password.

## Features

- Passwordless login (name + 10-digit mobile number)
- Home page with banner, category chips and trending products
- Product listing with category filter and search
- Product detail page with ratings, discount %, related products
- Cart (add / update quantity / remove)
- Checkout → Order placement → Order confirmation
- Order history per user
- Responsive, Flipkart-inspired blue/orange UI

## Tech stack

- Ruby on Rails 7.1 (MVC)
- SQLite3 database
- Server-rendered ERB views + plain CSS (`app/assets/stylesheets/application.css`)
- Session-based auth (`ApplicationController#current_user`)

## Project structure

```
app/
  controllers/   sessions, home, products, cart, orders
  models/        user, category, product, cart, cart_item, order, order_item
  views/         layouts, home, products, sessions, cart, orders, shared
  assets/        application.css (design tokens + components)
config/
  routes.rb, database.yml, application.rb, environments/*
db/
  migrate/*, schema.rb, seeds.rb
```

## Data model

| Model      | Key fields                                              |
|------------|----------------------------------------------------------|
| User       | phone_number (unique), name                               |
| Category   | name, icon                                                |
| Product    | name, description, price, mrp, image_url, stock, rating, category_id |
| Cart       | user_id (one per user)                                    |
| CartItem   | cart_id, product_id, quantity                              |
| Order      | user_id, total_amount, status (placed/shipped/delivered/cancelled), address |
| OrderItem  | order_id, product_id, quantity, price                      |

## Running it locally

This container has no internet access to RubyGems, so the Gemfile hasn't been bundled here. On your own machine, with Ruby 3.2+ and Bundler installed:

```bash
cd growkit
bundle install
bin/rails db:prepare    # creates db + runs migrations
bin/rails db:seed       # loads sample categories & products
bin/rails server         # visit http://localhost:3000
```

Log in with any name and any 10-digit number, e.g. `Priya Sharma` / `9876543210` — it will create your account on first login.

## Deploying to the cloud (Render)

The repo is already set up for [Render](https://render.com) — Postgres in production, SQLite stays for local dev.

**One-time local step first** (needed before any deploy, Rails needs this to encrypt sessions/secrets):
```bash
bundle install
EDITOR="nano" bin/rails credentials:edit
```
This creates `config/master.key` (gitignored — never commit it) and `config/credentials.yml.enc` (safe to commit). Commit and push the `.enc` file.

**Then deploy:**
1. Push the repo to GitHub (already done for `edith`).
2. In the Render dashboard → **New** → **Blueprint** → connect the repo. Render reads `render.yaml` and creates the web service + a free Postgres database automatically.
3. When prompted for `RAILS_MASTER_KEY`, paste the contents of your local `config/master.key` file.
4. Click **Apply** — Render runs `bin/render-build.sh` (installs gems, precompiles assets, runs migrations, seeds data on first deploy) and starts the app.
5. Your app is live at `https://growkit-<random>.onrender.com`.

Alternative: **Fly.io** works too and can keep SQLite (via a persistent volume) instead of switching to Postgres — good if you want to stay on a single instance and skip the database swap. Ask me and I can prep a `fly.toml` + Dockerfile instead.

## Notes / next steps

- Product images use placeholder.co URLs — swap in real images or Active Storage uploads.
- Payments aren't integrated; "Place order" just records the order.
- Add admin screens if you want to manage products/categories through the UI instead of `db/seeds.rb`.
