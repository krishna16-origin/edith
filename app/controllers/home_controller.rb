class HomeController < ApplicationController
  def index
    @categories = Category.all
    @products = Product.includes(:category).order(created_at: :desc).limit(12)
  end
end
