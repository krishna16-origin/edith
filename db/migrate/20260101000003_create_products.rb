class CreateProducts < ActiveRecord::Migration[7.1]
  def change
    create_table :products do |t|
      t.string :name, null: false
      t.text :description
      t.decimal :price, precision: 10, scale: 2, null: false
      t.decimal :mrp, precision: 10, scale: 2
      t.string :image_url
      t.integer :stock, default: 0
      t.decimal :rating, precision: 2, scale: 1, default: 4.0
      t.references :category, null: false, foreign_key: true
      t.timestamps
    end
  end
end
