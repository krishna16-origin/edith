class OrdersController < ApplicationController
  before_action :require_login

  def new
    @cart_items = current_cart.cart_items.includes(:product)
    redirect_to cart_path, alert: "Your cart is empty." if @cart_items.empty?
  end

  def create
    cart_items = current_cart.cart_items.includes(:product)

    if cart_items.empty?
      return redirect_to(cart_path, alert: "Your cart is empty.")
    end

    order = current_user.orders.build(
      total_amount: cart_items.sum { |i| i.product.price * i.quantity },
      address: params[:address],
      status: :placed
    )

    ActiveRecord::Base.transaction do
      order.save!
      cart_items.each do |item|
        order.order_items.create!(product: item.product, quantity: item.quantity, price: item.product.price)
        item.product.decrement!(:stock, item.quantity) if item.product.stock.to_i >= item.quantity
      end
      cart_items.destroy_all
    end

    redirect_to order_path(order), notice: "Order placed successfully!"
  rescue ActiveRecord::RecordInvalid => e
    redirect_to checkout_path_fallback, alert: e.message
  end

  def index
    @orders = current_user.orders.order(created_at: :desc)
  end

  def show
    @order = current_user.orders.find(params[:id])
  end

  private

  def checkout_path_fallback
    "/checkout"
  end
end
