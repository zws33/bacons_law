package com.zwsmith.bacons_law

import android.app.Application
import timber.log.Timber
import timber.log.Timber.Forest.plant


class BaconsLawApplication: Application() {

    override fun onCreate() {
        super.onCreate()

        if (BuildConfig.DEBUG) {
            plant(Timber.DebugTree())
        }
    }
}