package me.zwsmith.baconslaw

import android.app.Application
import timber.log.Timber
import timber.log.Timber.Forest.plant


class BaconsLawApplication : Application() {

  override fun onCreate() {
    super.onCreate()

    if (BuildConfig.DEBUG) {
      plant(Timber.DebugTree())
    }
  }
}
