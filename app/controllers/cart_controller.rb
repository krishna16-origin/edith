class CartController < ApplicationController
  before_action :require_login

  def show
    @cart_items = current_cart.cart_items.includes(product: :category)
  end

  def add_item
    product = Product.find(params[:product_id])
    item = current_cart.cart_items.find_or_initialize_by(product: product)
    item.quantity = item.new_record? ? 1 : item.quantity + 1
    item.save!
    redirect_back fallback_location: products_path, notice: "#{product.name} added to cart."
  end

  def update_item
    item = current_cart.cart_items.find(params[:id])
    quantity = params[:quantity].to_i

    if quantity <= 0
      item.destroy
    else
      item.update!(quantity: quantity)
    end

    redirect_to cart_path
  end

  def remove_item
    item = current_cart.cart_items.find(params[:id])
    item.destroy
    redirect_to cart_path, notice: "Item removed from cart."
  end
end
