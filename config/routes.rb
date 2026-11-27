Rails.application.routes.draw do
  root "home#index"

  get    "login",  to: "sessions#new"
  post   "login",  to: "sessions#create"
  delete "logout", to: "sessions#destroy"

  resources :products, only: [:index, :show]

  get    "cart",                 to: "cart#show"
  post   "cart/add/:product_id", to: "cart#add_item",   as: :add_to_cart
  patch  "cart/update/:id",      to: "cart#update_item", as: :update_cart_item
  delete "cart/remove/:id",      to: "cart#remove_item", as: :remove_cart_item

  get  "checkout",   to: "orders#new"
  post "orders",     to: "orders#create"
  get  "orders",     to: "orders#index"
  get  "orders/:id", to: "orders#show", as: :order
end
