class ApplicationController < ActionController::Base
  helper_method :current_user, :logged_in?, :current_cart

  private

  def current_user
    @current_user ||= User.find_by(id: session[:user_id])
  end

  def logged_in?
    current_user.present?
  end

  def current_cart
    return nil unless logged_in?
    current_user.cart || current_user.create_cart!
  end

  def require_login
    unless logged_in?
      redirect_to login_path, alert: "Please log in with your name and mobile number to continue."
    end
  end
end
