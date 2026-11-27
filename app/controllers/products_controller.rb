class ProductsController < ApplicationController
  def index
    @categories = Category.all
    @products = Product.includes(:category)
                        .in_category(params[:category_id])
                        .search(params[:query])
                        .order(created_at: :desc)
    @selected_category = Category.find_by(id: params[:category_id])
  end

  def show
    @product = Product.find(params[:id])
    @related = Product.where(category_id: @product.category_id)
                       .where.not(id: @product.id)
                       .limit(4)
  end
end
