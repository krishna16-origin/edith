class Product < ApplicationRecord
  belongs_to :category
  has_many :cart_items, dependent: :destroy
  has_many :order_items, dependent: :destroy

  validates :name, presence: true
  validates :price, presence: true, numericality: { greater_than: 0 }
  validates :stock, numericality: { greater_than_or_equal_to: 0 }

  scope :search, ->(query) { where("name LIKE ? OR description LIKE ?", "%#{query}%", "%#{query}%") if query.present? }
  scope :in_category, ->(category_id) { where(category_id: category_id) if category_id.present? }

  def in_stock?
    stock.to_i > 0
  end

  def discount_percent
    return 0 unless mrp.present? && mrp > price
    (((mrp - price) / mrp) * 100).round
  end
end
